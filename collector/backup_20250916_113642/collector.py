import sys
print(f"Using Python executable: {sys.executable}")
print(f"Python executable path: {sys.executable}")

import os
import sys
import math
import gzip
import json
import time
import random
import hashlib
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from jobspy import scrape_jobs
from supabase import create_client, Client
import csv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class CollectorConfig:
    """Production-optimized configuration for job collector"""
    
    # Database settings
    supabase_url: str = ""
    supabase_key: str = ""
    
    # Search settings - USA focused with major cities
    search_locations: List[str] = None
    search_terms: List[str] = None
    sites_priority: List[str] = None
    results_per_search: int = 100  # Increased for efficiency
    
    # Rate limiting - optimized for production
    min_delay_between_requests: int = 15  # Reduced for faster collection
    max_delay_between_requests: int = 45
    max_searches_per_site_per_day: int = 200  # Increased quota
    min_delay_between_sites: int = 30
    
    # Anti-detection
    user_agents: List[str] = None
    max_retries: int = 3
    exponential_backoff_base: float = 1.5
    
    # Processing - optimized for text encoding costs
    batch_size: int = 100  # Larger batches for efficiency
    hours_old: int = 48  # Reduced to focus on fresh jobs
    compress_descriptions: bool = True  # Enable compression
    max_description_length: int = 2000  # Limit description size
    
    # Modes
    debug_mode: bool = False
    dry_run: bool = False
    verbose_logging: bool = False
    
    # Progress saving
    progress_file: str = "collector_progress.json"
    
    def __post_init__(self):
        if self.search_locations is None:
            # USA-focused locations with major cities and remote
            self.search_locations = [
                "Remote",
                "United States",
                "New York, NY",
                "San Francisco, CA",
                "Los Angeles, CA",
                "Seattle, WA",
                "Austin, TX",
                "Dallas, TX",
                "Chicago, IL",
                "Boston, MA",
                "Denver, CO",
                "Atlanta, GA",
                "Miami, FL",
                "Washington, DC"
            ]
        
        if self.search_terms is None:
            # Optimized search terms for better results
            self.search_terms = [
                "software engineer",
                "senior software engineer",
                "full stack developer",
                "backend developer",
                "frontend developer",
                "data scientist",
                "data engineer",
                "devops engineer",
                "python developer",
                "javascript developer",
                "react developer",
                "node.js developer",
                "machine learning engineer",
                "cloud engineer",
                "software architect"
            ]
            
        if self.sites_priority is None:
            # Prioritize Indeed for best results with no rate limiting
            self.sites_priority = ["indeed", "zip_recruiter"]
            
        if self.user_agents is None:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
            ]
    
    @classmethod
    def from_env(cls) -> 'CollectorConfig':
        """Load configuration from environment variables"""
        config = cls()
        
        # Database
        config.supabase_url = os.getenv("SUPABASE_URL", "")
        config.supabase_key = (os.getenv("SUPABASE_SERVICE_KEY") or 
                              os.getenv("SUPABASE_KEY") or 
                              os.getenv("SUPABASE_API_KEY") or 
                              os.getenv("SUPABASE_ANON_KEY", ""))
        
        # Search settings
        if os.getenv("SEARCH_LOCATIONS"):
            config.search_locations = [loc.strip() for loc in os.getenv("SEARCH_LOCATIONS").split(",")]
        if os.getenv("SEARCH_TERMS"):
            config.search_terms = [term.strip() for term in os.getenv("SEARCH_TERMS").split(",")]
        if os.getenv("SITES_PRIORITY"):
            config.sites_priority = [site.strip() for site in os.getenv("SITES_PRIORITY").split(",")]
        
        config.results_per_search = int(os.getenv("RESULTS_PER_SEARCH", config.results_per_search))
        
        # Rate limiting
        config.min_delay_between_requests = int(os.getenv("MIN_DELAY_BETWEEN_REQUESTS", config.min_delay_between_requests))
        config.max_delay_between_requests = int(os.getenv("MAX_DELAY_BETWEEN_REQUESTS", config.max_delay_between_requests))
        config.max_searches_per_site_per_day = int(os.getenv("MAX_SEARCHES_PER_SITE_PER_DAY", config.max_searches_per_site_per_day))
        config.min_delay_between_sites = int(os.getenv("MIN_DELAY_BETWEEN_SITES", config.min_delay_between_sites))
        
        # Processing
        config.batch_size = int(os.getenv("BATCH_SIZE", config.batch_size))
        config.hours_old = int(os.getenv("HOURS_OLD", config.hours_old))
        config.compress_descriptions = os.getenv("COMPRESS_DESCRIPTIONS", "true").lower() == "true"
        config.max_description_length = int(os.getenv("MAX_DESCRIPTION_LENGTH", config.max_description_length))
        
        # Modes
        config.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        config.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        config.verbose_logging = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"
        
        return config

# Initialize configuration
config = CollectorConfig.from_env()

# Initialize Supabase client
supabase: Client = create_client(config.supabase_url, config.supabase_key)

# Setup optimized logging
log_level = logging.DEBUG if config.debug_mode else (logging.INFO if config.verbose_logging else logging.WARNING)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('collector.log') if not config.dry_run else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

# We'll use the Job class from jobspy directly

def compress_text(text: str) -> str:
    """Compress text using gzip to reduce storage costs"""
    if not text or not config.compress_descriptions:
        return text
    
    try:
        # Compress the text
        compressed = gzip.compress(text.encode('utf-8'))
        # Only use compression if it actually saves space
        if len(compressed) < len(text.encode('utf-8')) * 0.8:
            return compressed.hex()
        return text
    except Exception:
        return text

def truncate_description(description: str) -> str:
    """Truncate description to reduce text encoding costs"""
    if not description:
        return description
    
    # Truncate to max length
    if len(description) > config.max_description_length:
        description = description[:config.max_description_length] + "..."
    
    return description

def job_to_dict(job) -> dict:
    """Convert job object to optimized dictionary with null safety"""
    def clean_value(v):
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
    
    # Handle date_posted conversion
    date_posted_str = None
    if hasattr(job, 'date_posted') and job.date_posted:
        if isinstance(job.date_posted, date):
            date_posted_str = job.date_posted.isoformat()
        elif isinstance(job.date_posted, str) and job.date_posted.strip():
            date_posted_str = job.date_posted
    
    # Get and optimize description
    description = clean_value(getattr(job, 'description', None))
    if description:
        description = truncate_description(description)
        if config.compress_descriptions:
            description = compress_text(description)
    
    # Map to database schema with null safety
    job_dict = {
        "title": clean_value(getattr(job, 'title', None)),
        "company": clean_value(getattr(job, 'company', None)),
        "location": clean_value(getattr(job, 'location', None)),
        "salary": clean_value(getattr(job, 'salary', None)),
        "description": description,
        "url": clean_value(getattr(job, 'job_url', None)) or clean_value(getattr(job, 'url', None)),
        "date_posted": date_posted_str,
        "job_type": clean_value(getattr(job, 'job_type', None)),
        "remote": bool(getattr(job, 'remote', False)) if getattr(job, 'remote', None) is not None else False,
        "is_remote": bool(getattr(job, 'is_remote', False)) if getattr(job, 'is_remote', None) is not None else False,
        "job_url": clean_value(getattr(job, 'job_url', None)) or clean_value(getattr(job, 'url', None)),
        "country": "USA"  # Changed from US to USA for 3-char country code
    }
    return job_dict

class RateLimiter:
    """Production-optimized rate limiting with anti-detection"""
    
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.site_request_times = {}
        self.daily_request_counts = {}
        self.last_request_time = 0
        self.blocked_until = {}
        
    def can_make_request(self, site: str) -> bool:
        """Check if we can make a request to the given site"""
        current_time = time.time()
        today = datetime.now().date()
        
        # Check if site is temporarily blocked
        if site in self.blocked_until and current_time < self.blocked_until[site]:
            return False
        
        # Reset daily counts if it's a new day
        if today not in self.daily_request_counts:
            self.daily_request_counts = {today: {site: 0 for site in self.config.sites_priority}}
        elif today not in self.daily_request_counts:
            self.daily_request_counts[today] = {site: 0 for site in self.config.sites_priority}
        
        # Check daily quota
        daily_count = self.daily_request_counts.get(today, {}).get(site, 0)
        if daily_count >= self.config.max_searches_per_site_per_day:
            logger.warning(f"Daily quota reached for {site}: {daily_count}")
            return False
            
        # Check minimum delay between requests
        if current_time - self.last_request_time < self.config.min_delay_between_requests:
            return False
            
        return True
    
    def record_request(self, site: str, success: bool = True):
        """Record that a request was made to the site"""
        today = datetime.now().date()
        current_time = time.time()
        
        if today not in self.daily_request_counts:
            self.daily_request_counts[today] = {}
        
        self.daily_request_counts[today][site] = self.daily_request_counts[today].get(site, 0) + 1
        self.last_request_time = current_time
        self.site_request_times[site] = current_time
        
        # If request failed, implement temporary blocking
        if not success:
            block_duration = random.uniform(300, 900)  # 5-15 minutes
            self.blocked_until[site] = current_time + block_duration
            logger.warning(f"Temporarily blocking {site} for {block_duration/60:.1f} minutes")
        
    def wait_before_next_request(self, site: str):
        """Wait appropriate time before making the next request"""
        current_time = time.time()
        
        # Calculate jitter to avoid predictable patterns
        jitter = random.uniform(0.7, 1.3)
        
        # Minimum delay between requests
        min_delay = self.config.min_delay_between_requests * jitter
        
        # Additional delay between sites
        site_delay = 0
        if site in self.site_request_times:
            time_since_last_site_request = current_time - self.site_request_times[site]
            if time_since_last_site_request < self.config.min_delay_between_sites:
                site_delay = self.config.min_delay_between_sites - time_since_last_site_request
        
        # Random additional delay
        random_delay = random.uniform(self.config.min_delay_between_requests, self.config.max_delay_between_requests)
        
        total_delay = max(min_delay, site_delay, random_delay)
        
        if total_delay > 0:
            if config.verbose_logging:
                logger.info(f"Waiting {total_delay:.1f} seconds before next request to {site}")
            time.sleep(total_delay)

class JobDeduplicator:
    """Production-optimized job deduplication and batch processing"""
    
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.job_hashes = set()
        self.batch_jobs = []
        self.stats = {
            'total_found': 0,
            'duplicates_skipped': 0,
            'new_jobs_added': 0,
            'errors': 0,
            'text_savings': 0
        }
    
    def generate_job_hash(self, job_dict: dict) -> str:
        """Generate a unique hash for the job based on title, company, and location with null safety"""
        # Safely extract and clean values to prevent NoneType errors
        title = job_dict.get('title', '') or ''
        company = job_dict.get('company', '') or ''
        location = job_dict.get('location', '') or ''
        
        # Convert to strings and apply lower/strip safely
        key_parts = [
            str(title).lower().strip(),
            str(company).lower().strip(), 
            str(location).lower().strip()
        ]
        key = '|'.join(key_parts)
        return hashlib.md5(key.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, job_hash: str) -> bool:
        """Check if job hash already exists in database"""
        try:
            if not config.dry_run:
                existing = supabase.table("jobs").select("id").eq("job_hash", job_hash).limit(1).execute()
                return len(existing.data) > 0
            return job_hash in self.job_hashes
        except Exception as e:
            logger.error(f"Error checking for duplicate job: {e}")
            return False
    
    def add_job_batch(self, job_dict: dict):
        """Add job to batch for processing"""
        self.stats['total_found'] += 1
        
        # Calculate text savings from compression
        original_desc = job_dict.get('description', '')
        if original_desc and config.compress_descriptions and job_dict.get('description'):
            try:
                original_size = len(str(original_desc).encode('utf-8'))
                if isinstance(job_dict['description'], str):
                    compressed_size = len(job_dict['description'].encode('utf-8'))
                else:
                    compressed_size = len(bytes.fromhex(str(job_dict['description'])))
                self.stats['text_savings'] += max(0, original_size - compressed_size)
            except (TypeError, ValueError):
                pass  # Skip text savings calculation if there's an error
        
        job_hash = self.generate_job_hash(job_dict)
        job_dict['job_hash'] = job_hash
        
        if self.is_duplicate(job_hash):
            self.stats['duplicates_skipped'] += 1
            if config.debug_mode:
                logger.debug(f"Skipping duplicate: {job_dict.get('title')} at {job_dict.get('company')}")
            return
        
        self.job_hashes.add(job_hash)
        self.batch_jobs.append(job_dict)
        
        # Process batch if it reaches the configured size
        if len(self.batch_jobs) >= self.config.batch_size:
            self.process_batch()
    
    def process_batch(self):
        """Process and insert the current batch of jobs"""
        if not self.batch_jobs:
            return
            
        try:
            if not config.dry_run:
                # Insert batch into database
                result = supabase.table("jobs").insert(self.batch_jobs).execute()
                logger.info(f"Inserted batch of {len(self.batch_jobs)} jobs")
            else:
                logger.info(f"DRY RUN: Would insert batch of {len(self.batch_jobs)} jobs")
            
            self.stats['new_jobs_added'] += len(self.batch_jobs)
            
            # Log sample jobs in debug mode
            if config.debug_mode:
                for job in self.batch_jobs[:3]:  # Log first 3 jobs
                    logger.debug(f"Added: {job.get('title')} at {job.get('company')} ({job.get('location')})")
        
        except Exception as e:
            logger.error(f"Error processing job batch: {e}")
            self.stats['errors'] += len(self.batch_jobs)
        
        # Clear the batch
        self.batch_jobs.clear()
    
    def finalize(self):
        """Process any remaining jobs in the batch"""
        if self.batch_jobs:
            self.process_batch()
    
    def log_stats(self):
        """Log collection statistics"""
        logger.info("=== Collection Statistics ===")
        logger.info(f"Total jobs found: {self.stats['total_found']}")
        logger.info(f"New jobs added: {self.stats['new_jobs_added']}")
        logger.info(f"Duplicates skipped: {self.stats['duplicates_skipped']}")
        logger.info(f"Errors: {self.stats['errors']}")
        if self.stats['text_savings'] > 0:
            logger.info(f"Text compression savings: {self.stats['text_savings']/1024:.1f} KB")
        logger.info("============================")

def scrape_with_retry(site: str, search_term: str, location: str, rate_limiter: RateLimiter) -> Optional[Any]:
    """Scrape jobs with optimized retry logic and exponential backoff"""
    for attempt in range(config.max_retries):
        try:
            # Wait before making request
            rate_limiter.wait_before_next_request(site)
            
            # Check if we can make the request
            if not rate_limiter.can_make_request(site):
                logger.warning(f"Cannot make request to {site} due to rate limiting")
                return None
            
            # Get random user agent
            user_agent = random.choice(config.user_agents)
            
            if config.verbose_logging:
                logger.info(f"Scraping {site} for '{search_term}' in '{location}' (attempt {attempt + 1})")
            
            # Optimize JobSpy parameters for production efficiency
            scrape_params = {
                'site_name': [site],
                'search_term': search_term,
                'location': location,
                'results_wanted': config.results_per_search,
                'hours_old': config.hours_old,
                'country_indeed': 'USA',
                'is_remote': location.lower() == 'remote' if location else False,
                'verbose': 0 if not config.debug_mode else 1,
                'description_format': 'markdown'  # More compact than HTML
            }
            
            # Add site-specific optimizations
            if site == 'indeed':
                scrape_params.update({
                    'job_type': 'fulltime',  # Focus on full-time positions
                })
            elif site == 'zip_recruiter':
                scrape_params.update({
                    'distance': 25,  # Reasonable distance for better results
                })
            
            # Make the scraping request
            jobs = scrape_jobs(**scrape_params)
            
            # Record the successful request
            rate_limiter.record_request(site, success=True)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error scraping {site} (attempt {attempt + 1}): {e}")
            rate_limiter.record_request(site, success=False)
            
            if attempt < config.max_retries - 1:
                # Exponential backoff with jitter
                delay = config.exponential_backoff_base * (2 ** attempt)
                jitter = random.uniform(0.5, 1.5)
                total_delay = delay * jitter
                
                logger.info(f"Retrying in {total_delay:.1f} seconds...")
                time.sleep(total_delay)
            else:
                logger.error(f"Failed to scrape {site} after {config.max_retries} attempts")
                return None
    
    return None

def insert_jobs(jobs):
    """Legacy function - now deprecated in favor of JobDeduplicator"""
    logger.warning("insert_jobs() is deprecated. Use JobDeduplicator for production efficiency.")
    pass

def load_progress() -> dict:
    """Load collection progress from file"""
    try:
        if os.path.exists(config.progress_file):
            with open(config.progress_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load progress file: {e}")
    return {}

def save_progress(progress: dict):
    """Save collection progress to file"""
    try:
        with open(config.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save progress file: {e}")

def collect_jobs():
    """Production-optimized job collection with USA focus and text compression"""
    logger.info("Starting production job collection (USA focused)...")
    
    if not config.supabase_url or not config.supabase_key:
        logger.error("Supabase credentials not configured. Set SUPABASE_URL and SUPABASE_KEY environment variables.")
        return
    
    # Initialize production components
    rate_limiter = RateLimiter(config)
    deduplicator = JobDeduplicator(config)
    
    # Track progress for resuming
    progress = load_progress()
    completed_combinations = progress.get('completed', [])
    progress_key = f"{datetime.now().date()}"
    
    # Calculate total combinations for progress tracking
    total_combinations = len(config.search_terms) * len(config.search_locations) * len(config.sites_priority)
    processed_combinations = 0
    
    logger.info(f"Processing {total_combinations} search combinations across {len(config.sites_priority)} sites")
    logger.info(f"Target locations: {len(config.search_locations)} USA cities + Remote")
    logger.info(f"Search terms: {len(config.search_terms)} tech roles")
    
    start_time = time.time()
    
    try:
        # Iterate through all combinations with USA focus
        for search_term in config.search_terms:
            for location in config.search_locations:
                for site in config.sites_priority:
                    combination_key = f"{site}_{search_term}_{location}_{progress_key}"
                    
                    # Skip if already processed today
                    if combination_key in completed_combinations:
                        if config.debug_mode:
                            logger.debug(f"Skipping processed: {combination_key}")
                        processed_combinations += 1
                        continue
                    
                    logger.info(f"Processing: {site} | {search_term} | {location}")
                    
                    # Scrape jobs with optimized retry logic
                    jobs_df = scrape_with_retry(site, search_term, location, rate_limiter)
                    
                    if jobs_df is not None and len(jobs_df) > 0:
                        logger.info(f"Found {len(jobs_df)} jobs from {site}")
                        
                        # Convert DataFrame to job objects and process
                        for _, job_row in jobs_df.iterrows():
                            job_obj = type('Job', (), {})()
                            for key, value in job_row.items():
                                setattr(job_obj, key, value)
                            
                            job_dict = job_to_dict(job_obj)
                            deduplicator.add_job_batch(job_dict)
                    else:
                        if config.verbose_logging:
                            logger.warning(f"No jobs found: {site} | {search_term} | {location}")
                    
                    # Mark combination as completed
                    completed_combinations.append(combination_key)
                    processed_combinations += 1
                    
                    # Save progress periodically
                    if processed_combinations % 20 == 0:
                        save_progress({'completed': completed_combinations})
                        elapsed = time.time() - start_time
                        rate = processed_combinations / elapsed * 3600  # combinations per hour
                        logger.info(f"Progress: {processed_combinations}/{total_combinations} ({processed_combinations/total_combinations*100:.1f}%) - Rate: {rate:.1f}/hour")
        
        # Finalize any remaining jobs in batch
        deduplicator.finalize()
        
        # Log final statistics
        elapsed_time = time.time() - start_time
        deduplicator.log_stats()
        logger.info(f"Collection completed in {elapsed_time/60:.1f} minutes")
        logger.info(f"Average rate: {processed_combinations/(elapsed_time/3600):.1f} combinations/hour")
        
        # Save final progress
        save_progress({'completed': completed_combinations, 'last_run': datetime.now().isoformat()})
        
        # Optional: Save sample to CSV for debugging
        if config.debug_mode and deduplicator.stats['new_jobs_added'] > 0:
            try:
                sample_jobs = deduplicator.batch_jobs[:10] if deduplicator.batch_jobs else []
                if sample_jobs:
                    import pandas as pd
                    df = pd.DataFrame(sample_jobs)
                    df.to_csv("sample_jobs.csv", index=False)
                    logger.info("Saved sample jobs to sample_jobs.csv")
            except Exception as e:
                logger.warning(f"Could not save sample CSV: {e}")
        
    except KeyboardInterrupt:
        logger.info("Collection interrupted by user")
        deduplicator.finalize()
        save_progress({'completed': completed_combinations})
        
    except Exception as e:
        logger.error(f"Unexpected error during collection: {e}")
        deduplicator.finalize()
        save_progress({'completed': completed_combinations})

if __name__ == "__main__":
    # Production entry point with configuration logging
    logger.info(f"Starting collector with configuration:")
    logger.info(f"- Sites: {config.sites_priority}")
    logger.info(f"- Locations: {len(config.search_locations)} USA cities")
    logger.info(f"- Search terms: {len(config.search_terms)} roles")
    logger.info(f"- Results per search: {config.results_per_search}")
    logger.info(f"- Batch size: {config.batch_size}")
    logger.info(f"- Text compression: {config.compress_descriptions}")
    logger.info(f"- Max description length: {config.max_description_length}")
    logger.info(f"- Dry run: {config.dry_run}")
    
    collect_jobs()
