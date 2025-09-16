"""
Configuration management for distributed job collection
Handles environment-specific settings and validation
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class SiteQuotaConfig:
    """Configuration for site-specific quotas and limits"""
    daily_limit: int
    hourly_limit: int
    requests_per_minute: int
    cool_down_minutes: int
    requires_proxy: bool = False
    priority: int = 1  # Lower = higher priority

@dataclass
class CollectionConfig:
    """Main configuration for job collection system"""
    
    # Database settings
    supabase_url: str = ""
    supabase_key: str = ""
    
    # Collection strategy
    max_jobs_per_run: int = 500
    max_jobs_per_search: int = 50
    hours_old_filter: int = 48
    batch_size: int = 100
    
    # Rate limiting
    base_delay_seconds: int = 5
    max_delay_seconds: int = 30
    exponential_backoff: bool = True
    
    # Site configurations
    site_quotas: Dict[str, SiteQuotaConfig] = None
    
    # Search parameters
    default_locations: List[str] = None
    search_term_categories: Dict[str, List[str]] = None
    
    # Proxy settings
    proxy_rotation: bool = True
    proxy_list: List[str] = None
    
    # Quality settings
    min_company_match_rate: float = 0.7
    enable_company_extraction: bool = True
    enable_duplicate_detection: bool = True
    
    # Monitoring
    enable_alerts: bool = True
    alert_thresholds: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.site_quotas is None:
            self.site_quotas = {
                'indeed': SiteQuotaConfig(
                    daily_limit=300,
                    hourly_limit=50,
                    requests_per_minute=2,
                    cool_down_minutes=5,
                    priority=1
                ),
                'linkedin': SiteQuotaConfig(
                    daily_limit=100,
                    hourly_limit=15,
                    requests_per_minute=1,
                    cool_down_minutes=10,
                    requires_proxy=True,
                    priority=2
                ),
                'glassdoor': SiteQuotaConfig(
                    daily_limit=150,
                    hourly_limit=25,
                    requests_per_minute=1,
                    cool_down_minutes=8,
                    priority=3
                ),
                'google': SiteQuotaConfig(
                    daily_limit=100,
                    hourly_limit=20,
                    requests_per_minute=1,
                    cool_down_minutes=12,
                    priority=4
                ),
                'zip_recruiter': SiteQuotaConfig(
                    daily_limit=200,
                    hourly_limit=35,
                    requests_per_minute=2,
                    cool_down_minutes=6,
                    priority=5
                )
            }
        
        if self.default_locations is None:
            self.default_locations = [
                "Remote",
                "San Francisco, CA",
                "New York, NY", 
                "Seattle, WA",
                "Austin, TX",
                "Boston, MA",
                "Los Angeles, CA",
                "Chicago, IL",
                "Denver, CO",
                "Washington, DC"
            ]
        
        if self.search_term_categories is None:
            self.search_term_categories = {
                'software_engineering': [
                    'software engineer',
                    'senior software engineer',
                    'staff software engineer',
                    'principal software engineer',	
                    'software architect',
                    'full stack developer',
                    'backend developer',
                    'frontend developer',
                    'full stack engineer'
                ],
                'data_and_ai': [
                    'data scientist',
                    'senior data scientist',
                    'data engineer',
                    'machine learning engineer',
                    'AI engineer',
                    'data analyst',
                    'analytics engineer',
                    'research scientist'
                ],
                'infrastructure': [
                    'devops engineer',
                    'site reliability engineer',
                    'cloud engineer',
                    'infrastructure engineer',
                    'platform engineer',
                    'security engineer',
                    'systems engineer'
                ],
                'specialized': [
                    'mobile developer',
                    'ios developer',
                    'android developer',
                    'react developer',
                    'python developer',
                    'javascript developer',
                    'node.js developer',
                    'go developer'
                ]
            }
        
        if self.alert_thresholds is None:
            self.alert_thresholds = {
                'min_daily_jobs': 100,
                'max_missing_company_rate': 0.3,
                'max_hours_without_collection': 6,
                'min_site_success_rate': 0.5,
                'max_error_rate': 0.1
            }

class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_file: Optional[str] = None):
        load_dotenv()
        self.config_file = config_file
        self._config = None
    
    def get_config(self) -> CollectionConfig:
        """Get current configuration, loading from environment if needed"""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def _load_config(self) -> CollectionConfig:
        """Load configuration from environment variables and files"""
        config = CollectionConfig()
        
        # Database settings
        config.supabase_url = os.getenv("SUPABASE_URL", "")
        config.supabase_key = (
            os.getenv("SUPABASE_SERVICE_KEY") or 
            os.getenv("SUPABASE_KEY") or
            os.getenv("SUPABASE_API_KEY", "")
        )
        
        # Collection settings
        config.max_jobs_per_run = int(os.getenv("MAX_JOBS_PER_RUN", config.max_jobs_per_run))
        config.max_jobs_per_search = int(os.getenv("MAX_JOBS_PER_SEARCH", config.max_jobs_per_search))
        config.hours_old_filter = int(os.getenv("HOURS_OLD_FILTER", config.hours_old_filter))
        config.batch_size = int(os.getenv("BATCH_SIZE", config.batch_size))
        
        # Proxy settings
        proxy_list_env = os.getenv("PROXY_LIST", "")
        if proxy_list_env:
            config.proxy_list = [p.strip() for p in proxy_list_env.split(",") if p.strip()]
        
        # Override locations if specified
        locations_env = os.getenv("SEARCH_LOCATIONS", "")
        if locations_env:
            config.default_locations = [loc.strip() for loc in locations_env.split(",")]
        
        # Quality settings
        config.min_company_match_rate = float(os.getenv("MIN_COMPANY_MATCH_RATE", config.min_company_match_rate))
        config.enable_company_extraction = os.getenv("ENABLE_COMPANY_EXTRACTION", "true").lower() == "true"
        config.enable_duplicate_detection = os.getenv("ENABLE_DUPLICATE_DETECTION", "true").lower() == "true"
        
        # Load from file if specified
        if self.config_file and os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    self._merge_file_config(config, file_config)
            except Exception as e:
                logger.error(f"Error loading config file {self.config_file}: {str(e)}")
        
        # Validate configuration
        self._validate_config(config)
        
        return config
    
    def _merge_file_config(self, config: CollectionConfig, file_config: Dict[str, Any]):
        """Merge file-based configuration with environment config"""
        # This could be expanded to handle complex file-based configurations
        for key, value in file_config.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    def _validate_config(self, config: CollectionConfig):
        """Validate configuration settings"""
        errors = []
        
        if not config.supabase_url:
            errors.append("SUPABASE_URL is required")
        
        if not config.supabase_key:
            errors.append("SUPABASE_SERVICE_KEY is required")
        
        if config.max_jobs_per_run <= 0:
            errors.append("MAX_JOBS_PER_RUN must be positive")
        
        if config.min_company_match_rate < 0 or config.min_company_match_rate > 1:
            errors.append("MIN_COMPANY_MATCH_RATE must be between 0 and 1")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
        
        logger.info("Configuration validation passed")
    
    def save_config(self, config: CollectionConfig, file_path: str):
        """Save configuration to file"""
        try:
            config_dict = asdict(config)
            with open(file_path, 'w') as f:
                json.dump(config_dict, f, indent=2, default=str)
            logger.info(f"Configuration saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            raise
    
    def get_site_config(self, site_name: str) -> Optional[SiteQuotaConfig]:
        """Get configuration for a specific site"""
        config = self.get_config()
        return config.site_quotas.get(site_name)
    
    def get_search_terms_by_category(self, categories: List[str]) -> List[str]:
        """Get search terms for specified categories"""
        config = self.get_config()
        terms = []
        
        for category in categories:
            if category in config.search_term_categories:
                terms.extend(config.search_term_categories[category])
        
        return list(set(terms))  # Remove duplicates

# Global config manager instance
config_manager = ConfigManager()
