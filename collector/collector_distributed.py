"""
Distributed job collector script for GitHub Actions workflows
Handles quota management and distributed collection strategies
"""

import os
import sys
import json
import time
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enhanced_collector import EnhancedJobCollector, SEARCH_STRATEGIES, get_recommended_search_terms
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('collector_distributed.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DistributedJobCollector:
    """Orchestrates distributed job collection across multiple workflows"""
    
    def __init__(self):
        self.supabase = self._init_supabase()
        self.collector = EnhancedJobCollector()
        self.batch_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getenv('BATCH_IDENTIFIER', 'default')}"
        
    def _init_supabase(self) -> Client:
        """Initialize Supabase client"""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not url or not key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")
        
        return create_client(url, key)
    
    def run_collection(self):
        """Main collection runner based on environment configuration"""
        try:
            # Get configuration from environment
            strategy = os.getenv('COLLECTION_STRATEGY', 'comprehensive')
            sites = os.getenv('SITES_PRIORITY', '').split(',') if os.getenv('SITES_PRIORITY') else None
            max_jobs = int(os.getenv('MAX_JOBS_PER_RUN', '500'))
            search_focus = os.getenv('SEARCH_FOCUS', '').split(',') if os.getenv('SEARCH_FOCUS') else None
            
            logger.info(f"Starting collection with strategy: {strategy}, max_jobs: {max_jobs}")
            
            # Load search terms based on focus
            search_terms = self._get_search_terms(search_focus)
            locations = self._get_locations()
            
            total_collected = 0
            batch_results = []
            
            # Collect jobs using specified strategy
            for location in locations:
                if total_collected >= max_jobs:
                    break
                    
                for search_term in search_terms:
                    if total_collected >= max_jobs:
                        break
                    
                    try:
                        # Calculate how many jobs to request for this search
                        remaining = max_jobs - total_collected
                        results_wanted = min(50, remaining)  # Max 50 per search
                        
                        logger.info(f"Searching: '{search_term}' in {location} (want {results_wanted})")
                        
                        # Use smart scraping with site selection
                        jobs = self.collector.scrape_jobs_smart(
                            search_term=search_term,
                            location=location,
                            results_wanted=results_wanted,
                            hours_old=48,
                            site_name=sites[0] if sites and len(sites) == 1 else None
                        )
                        
                        if jobs:
                            # Process and store jobs
                            processed_count = self._process_and_store_jobs(jobs, search_term, location)
                            total_collected += processed_count
                            
                            batch_results.append({
                                'search_term': search_term,
                                'location': location,
                                'jobs_found': len(jobs),
                                'jobs_stored': processed_count
                            })
                            
                            logger.info(f"Stored {processed_count} jobs. Total: {total_collected}/{max_jobs}")
                        
                        # Rate limiting between searches
                        time.sleep(random.randint(5, 15))
                        
                    except Exception as e:
                        logger.error(f"Error in search '{search_term}' at {location}: {str(e)}")
                        continue
            
            # Log final results
            self._log_collection_summary(total_collected, batch_results)
            
            # Update quota tracking
            self._update_quota_tracking()
            
            return total_collected
            
        except Exception as e:
            logger.error(f"Fatal error in collection: {str(e)}")
            raise
    
    def _get_search_terms(self, search_focus: Optional[List[str]] = None) -> List[str]:
        """Get search terms based on focus areas"""
        all_terms = get_recommended_search_terms()
        
        if search_focus:
            # Use only specified focus areas
            terms = []
            for focus in search_focus:
                if focus in all_terms:
                    terms.extend(all_terms[focus])
            return terms[:10]  # Limit to prevent too many requests
        else:
            # Use all categories but limit total
            terms = []
            for category_terms in all_terms.values():
                terms.extend(category_terms[:3])  # Max 3 per category
            return terms[:12]
    
    def _get_locations(self) -> List[str]:
        """Get locations for job search"""
        env_locations = os.getenv('SEARCH_LOCATIONS')
        if env_locations:
            return [loc.strip() for loc in env_locations.split(',')]
        
        # Default high-value locations
        return [
            "Remote",
            "San Francisco, CA", 
            "New York, NY",
            "Seattle, WA",
            "Austin, TX",
            "Boston, MA"
        ]
    
    def _process_and_store_jobs(self, jobs: List[Dict[str, Any]], search_term: str, location: str) -> int:
        """Process jobs and store them in database"""
        if not jobs:
            return 0
        
        stored_count = 0
        batch_data = []
        
        for job in jobs:
            try:
                # Add collection metadata
                job['batch_id'] = self.batch_id
                job['search_term_used'] = search_term
                job['location_searched'] = location
                job['collected_at'] = datetime.now().isoformat()
                
                # Generate hash for deduplication
                job_hash = self._generate_job_hash(job)
                job['job_url_hash'] = job_hash
                
                batch_data.append(job)
                
            except Exception as e:
                logger.error(f"Error processing job: {str(e)}")
                continue
        
        # Store batch in database
        if batch_data:
            try:
                # Use upsert to handle duplicates gracefully
                result = self.supabase.table('jobs').upsert(
                    batch_data,
                    on_conflict='job_url_hash'
                ).execute()
                
                stored_count = len(batch_data)
                logger.info(f"Successfully stored batch of {stored_count} jobs")
                
            except Exception as e:
                logger.error(f"Error storing jobs batch: {str(e)}")
                # Try individual inserts as fallback
                stored_count = self._store_jobs_individually(batch_data)
        
        return stored_count
    
    def _store_jobs_individually(self, jobs: List[Dict[str, Any]]) -> int:
        """Fallback method to store jobs individually"""
        stored_count = 0
        
        for job in jobs:
            try:
                self.supabase.table('jobs').upsert(job, on_conflict='job_url_hash').execute()
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing individual job: {str(e)}")
                continue
        
        logger.info(f"Stored {stored_count} jobs individually")
        return stored_count
    
    def _generate_job_hash(self, job: Dict[str, Any]) -> str:
        """Generate unique hash for job deduplication"""
        import hashlib
        
        # Use job URL as primary identifier, fall back to title+company+location
        if job.get('job_url'):
            hash_string = job['job_url']
        else:
            hash_string = f"{job.get('title', '')}{job.get('company', '')}{job.get('location', '')}"
        
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def _log_collection_summary(self, total_collected: int, batch_results: List[Dict]):
        """Log collection summary"""
        logger.info("="*50)
        logger.info("COLLECTION SUMMARY")
        logger.info("="*50)
        logger.info(f"Batch ID: {self.batch_id}")
        logger.info(f"Total Jobs Collected: {total_collected}")
        logger.info(f"Search Combinations: {len(batch_results)}")
        
        # Site usage summary
        quota_status = self.collector.get_quota_status()
        logger.info("\nSite Usage:")
        for site, status in quota_status.items():
            logger.info(f"  {site}: {status['used']}/{status['limit']} ({status['remaining']} remaining)")
        
        # Top performing searches
        if batch_results:
            sorted_results = sorted(batch_results, key=lambda x: x['jobs_stored'], reverse=True)
            logger.info("\nTop Performing Searches:")
            for result in sorted_results[:5]:
                logger.info(f"  '{result['search_term']}' in {result['location']}: {result['jobs_stored']} jobs")
    
    def _update_quota_tracking(self):
        """Update quota tracking in database"""
        try:
            quota_data = {
                'date': datetime.now().date().isoformat(),
                'batch_id': self.batch_id,
                'site_usage': self.collector.get_quota_status(),
                'updated_at': datetime.now().isoformat()
            }
            
            self.supabase.table('quota_tracking').upsert(
                quota_data,
                on_conflict='date,batch_id'
            ).execute()
            
        except Exception as e:
            logger.error(f"Error updating quota tracking: {str(e)}")

def main():
    """Main entry point"""
    try:
        collector = DistributedJobCollector()
        total_jobs = collector.run_collection()
        
        print(f"Collection completed successfully. Total jobs: {total_jobs}")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Collection failed: {str(e)}")
        print(f"Collection failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
