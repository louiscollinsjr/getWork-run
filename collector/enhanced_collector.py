"""
Enhanced job collector with LinkedIn, Glassdoor support and quota management
"""

import os
import time
import random
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from jobspy import scrape_jobs
from data_validator import validate_job_batch

logger = logging.getLogger(__name__)

@dataclass
class SiteConfig:
    """Configuration for individual job sites"""
    name: str
    daily_quota: int
    min_delay: int
    max_delay: int
    priority: int  # Lower number = higher priority
    requires_proxy: bool = False
    special_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.special_params is None:
            self.special_params = {}

class EnhancedJobCollector:
    """Enhanced job collector with multi-site support and quota management"""
    
    def __init__(self):
        self.site_configs = {
            'indeed': SiteConfig(
                name='indeed',
                daily_quota=300,  # Increased quota
                min_delay=10,
                max_delay=20,
                priority=1,  # Highest priority - most reliable
                requires_proxy=False
            ),
            'linkedin': SiteConfig(
                name='linkedin',
                daily_quota=100,  # Conservative due to rate limiting
                min_delay=30,
                max_delay=60,
                priority=2,  # High priority for tech jobs
                requires_proxy=True,  # LinkedIn requires proxies
                special_params={
                    'linkedin_fetch_description': True,  # Get detailed info
                }
            ),
            'glassdoor': SiteConfig(
                name='glassdoor',
                daily_quota=150,
                min_delay=20,
                max_delay=40,
                priority=3,
                requires_proxy=False,
                special_params={
                    'country_indeed': 'USA'  # Required for Glassdoor
                }
            ),
            'google': SiteConfig(
                name='google',
                daily_quota=100,  # Conservative - Google can be finicky
                min_delay=25,
                max_delay=50,
                priority=4,
                requires_proxy=False,
                special_params={
                    'google_search_term': None  # Will be set dynamically
                }
            ),
            'zip_recruiter': SiteConfig(
                name='zip_recruiter',
                daily_quota=200,
                min_delay=15,
                max_delay=30,
                priority=5,  # Lower priority
                requires_proxy=False
            )
        }
        
        # Track daily usage
        self.daily_usage = {site: 0 for site in self.site_configs.keys()}
        
        # Proxy configuration
        self.proxies = self._load_proxies()
        
    def _load_proxies(self) -> List[str]:
        """Load proxy list from environment or file"""
        proxy_env = os.getenv('PROXY_LIST', '')
        if proxy_env:
            return [p.strip() for p in proxy_env.split(',') if p.strip()]
        
        # Try to load from file
        proxy_file = os.path.join(os.path.dirname(__file__), 'proxies.txt')
        if os.path.exists(proxy_file):
            with open(proxy_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        
        logger.warning("No proxies configured. LinkedIn may have limited success.")
        return []
    
    def scrape_jobs_smart(
        self,
        search_term: str,
        location: str,
        results_wanted: int = 50,
        hours_old: int = 48,
        site_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Smart job scraping with site selection and quota management
        """
        all_jobs = []
        
        # Determine which sites to use
        if site_name:
            sites_to_try = [site_name] if site_name in self.site_configs else []
        else:
            # Use all available sites in priority order
            sites_to_try = sorted(
                [s for s in self.site_configs.keys() if self.daily_usage[s] < self.site_configs[s].daily_quota],
                key=lambda x: self.site_configs[x].priority
            )
        
        if not sites_to_try:
            logger.warning("No sites available due to quota limits")
            return []
        
        for site in sites_to_try:
            if self.daily_usage[site] >= self.site_configs[site].daily_quota:
                logger.info(f"Skipping {site} - daily quota reached")
                continue
            
            try:
                jobs = self._scrape_single_site(
                    site=site,
                    search_term=search_term,
                    location=location,
                    results_wanted=min(results_wanted, self.site_configs[site].daily_quota - self.daily_usage[site]),
                    hours_old=hours_old
                )
                
                if jobs is not None and not jobs.empty:
                    # Validate and normalize jobs
                    normalized_jobs = validate_job_batch(jobs.to_dict('records') if hasattr(jobs, 'to_dict') else jobs)
                    all_jobs.extend(normalized_jobs)
                    self.daily_usage[site] += len(normalized_jobs)
                    
                    logger.info(f"Collected {len(normalized_jobs)} jobs from {site}")
                
                # Delay between sites
                delay = random.randint(
                    self.site_configs[site].min_delay,
                    self.site_configs[site].max_delay
                )
                logger.debug(f"Waiting {delay}s before next site...")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error scraping {site}: {str(e)}")
                continue
        
        return all_jobs
    
    def _scrape_single_site(
        self,
        site: str,
        search_term: str,
        location: str,
        results_wanted: int,
        hours_old: int
    ) -> Any:
        """Scrape a single job site with site-specific configuration"""
        
        config = self.site_configs[site]
        
        # Build parameters
        params = {
            'site_name': [site],
            'search_term': search_term,
            'location': location,
            'results_wanted': results_wanted,
            'hours_old': hours_old,
            'verbose': 1,  # Reduce verbosity
        }
        
        # Add site-specific parameters
        params.update(config.special_params)
        
        # Handle Google search term special case
        if site == 'google':
            params['google_search_term'] = f"{search_term} jobs near {location} since yesterday"
        
        # Add proxies if required
        if config.requires_proxy and self.proxies:
            params['proxies'] = self.proxies
        
        # User agent rotation
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        params['user_agent'] = random.choice(user_agents)
        
        logger.info(f"Scraping {site} for '{search_term}' in {location} (want {results_wanted} jobs)")
        
        try:
            result = scrape_jobs(**params)
            return result
        except Exception as e:
            logger.error(f"Error scraping {site}: {str(e)}")
            # Return empty DataFrame to maintain consistent return type
            import pandas as pd
            return pd.DataFrame()
    
    def get_quota_status(self) -> Dict[str, Dict[str, int]]:
        """Get current quota usage status"""
        status = {}
        for site, config in self.site_configs.items():
            status[site] = {
                'used': self.daily_usage[site],
                'limit': config.daily_quota,
                'remaining': config.daily_quota - self.daily_usage[site]
            }
        return status
    
    def reset_daily_usage(self):
        """Reset daily usage counters (called daily)"""
        self.daily_usage = {site: 0 for site in self.site_configs.keys()}
        logger.info("Daily usage counters reset")

# Configuration for different search strategies
SEARCH_STRATEGIES = {
    'high_volume': {
        'sites': ['indeed', 'zip_recruiter', 'glassdoor'],
        'results_per_site': 100,
        'description': 'High volume collection from reliable sources'
    },
    'quality_focused': {
        'sites': ['linkedin', 'glassdoor', 'indeed'],
        'results_per_site': 50,
        'description': 'Quality-focused collection from premium sources'
    },
    'comprehensive': {
        'sites': ['indeed', 'linkedin', 'glassdoor', 'google', 'zip_recruiter'],
        'results_per_site': 40,
        'description': 'Comprehensive collection from all sources'
    },
    'tech_focused': {
        'sites': ['linkedin', 'indeed', 'glassdoor'],
        'results_per_site': 75,
        'description': 'Tech job focused collection'
    }
}

def get_recommended_search_terms() -> Dict[str, List[str]]:
    """Get recommended search terms by category"""
    return {
        'software_engineering': [
            'software engineer',
            'senior software engineer', 
            'staff software engineer',
            'principal software engineer',
            'software architect',
            'full stack developer',
            'backend developer',
            'frontend developer'
        ],
        'data_and_ai': [
            'data scientist',
            'senior data scientist',
            'data engineer',
            'machine learning engineer',
            'AI engineer',
            'data analyst',
            'analytics engineer'
        ],
        'infrastructure': [
            'devops engineer',
            'site reliability engineer',
            'cloud engineer',
            'infrastructure engineer',
            'platform engineer',
            'security engineer'
        ],
        'specialized': [
            'mobile developer',
            'ios developer', 
            'android developer',
            'react developer',
            'python developer',
            'javascript developer',
            'node.js developer'
        ]
    }
