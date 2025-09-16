"""
Data validation and normalization utilities for job scraping
Handles null company values and data quality issues
"""

import re
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class JobDataValidator:
    """Validates and normalizes job data before database insertion"""
    
    def __init__(self):
        # Common company patterns to extract from URLs or descriptions
        self.company_patterns = [
            r'https://.*?\.(\w+)\.com',
            r'@(\w+)\.(?:com|org|net)',
            r'(?:at|with|for)\s+([A-Z][a-zA-Z\s]+?)(?:\s|,|\.)',
        ]
        
        # Known job board domains to avoid as company names
        self.job_board_domains = {
            'indeed.com', 'linkedin.com', 'glassdoor.com', 
            'ziprecruiter.com', 'monster.com', 'careerbuilder.com'
        }
    
    def normalize_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and validate a single job record
        Returns the normalized job or None if validation fails
        """
        try:
            # Create a copy to avoid modifying original
            normalized = job_data.copy()
            
            # Handle null/empty company
            if not normalized.get('company') or str(normalized.get('company')).strip() in ['', 'null', 'None']:
                normalized['company'] = self._extract_company_name(normalized)
            
            # Clean and validate company name
            if normalized.get('company'):
                normalized['company'] = self._clean_company_name(normalized['company'])
            
            # If still no company, set to "Unknown Company"
            if not normalized.get('company'):
                normalized['company'] = "Unknown Company"
                logger.warning(f"No company found for job: {normalized.get('title', 'Unknown')} at {normalized.get('job_url', 'Unknown URL')}")
            
            # Normalize other fields
            normalized = self._normalize_location(normalized)
            normalized = self._normalize_salary(normalized)
            normalized = self._clean_description(normalized)
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing job data: {str(e)}")
            return None
    
    def _extract_company_name(self, job_data: Dict[str, Any]) -> Optional[str]:
        """Try to extract company name from various sources"""
        
        # Try job URL first
        if job_data.get('job_url'):
            company = self._extract_from_url(job_data['job_url'])
            if company:
                return company
        
        # Try description
        if job_data.get('description'):
            company = self._extract_from_description(job_data['description'])
            if company:
                return company
        
        # Try company_url if available
        if job_data.get('company_url'):
            company = self._extract_from_url(job_data['company_url'])
            if company:
                return company
        
        return None
    
    def _extract_from_url(self, url: str) -> Optional[str]:
        """Extract company name from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Skip job board domains
            if any(job_board in domain for job_board in self.job_board_domains):
                return None
            
            # Extract company from subdomain or domain
            if domain.startswith('jobs.'):
                # jobs.company.com pattern
                parts = domain.split('.')
                if len(parts) >= 2:
                    return parts[1].title()
            elif domain.count('.') >= 2:
                # company.jobs.com or similar
                parts = domain.split('.')
                return parts[0].title()
            else:
                # Simple domain like company.com
                company = domain.split('.')[0]
                return company.title()
                
        except Exception as e:
            logger.debug(f"Error extracting from URL {url}: {str(e)}")
        
        return None
    
    def _extract_from_description(self, description: str) -> Optional[str]:
        """Extract company name from job description"""
        if not description:
            return None
            
        # Look for common patterns
        patterns = [
            r'(?:join|at)\s+([A-Z][a-zA-Z\s&]+?)(?:\s+(?:is|as|in|and|,))',
            r'([A-Z][a-zA-Z\s&]+?)\s+is\s+(?:looking|seeking|hiring)',
            r'Company:\s*([A-Za-z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+?)\s+offers',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, description[:500])  # Search first 500 chars
            if matches:
                company = matches[0].strip()
                if len(company) > 2 and len(company) < 50:  # Reasonable length
                    return company
        
        return None
    
    def _clean_company_name(self, company: str) -> str:
        """Clean and standardize company name"""
        if not company:
            return "Unknown Company"
        
        # Remove common suffixes and clean
        company = str(company).strip()
        company = re.sub(r'\b(?:Inc|LLC|Ltd|Corp|Corporation|Company|Co)\b\.?', '', company, flags=re.IGNORECASE)
        company = re.sub(r'\s+', ' ', company).strip()
        
        # Capitalize properly
        if company.isupper() or company.islower():
            company = company.title()
        
        return company or "Unknown Company"
    
    def _normalize_location(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize location fields"""
        # Ensure location components are strings
        for field in ['city', 'state', 'country']:
            if job_data.get(field) and job_data[field] != 'null':
                job_data[field] = str(job_data[field]).strip()
            else:
                job_data[field] = None
        
        return job_data
    
    def _normalize_salary(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize salary information"""
        # Convert salary fields to proper types
        for field in ['min_amount', 'max_amount']:
            if job_data.get(field):
                try:
                    job_data[field] = float(job_data[field])
                except (ValueError, TypeError):
                    job_data[field] = None
        
        return job_data
    
    def _clean_description(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and truncate description if needed"""
        if job_data.get('description'):
            desc = str(job_data['description'])
            # Remove excessive whitespace
            desc = re.sub(r'\s+', ' ', desc).strip()
            # Truncate if too long (for cost optimization)
            if len(desc) > 2000:
                desc = desc[:1997] + "..."
            job_data['description'] = desc
        
        return job_data

def validate_job_batch(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and normalize a batch of jobs"""
    validator = JobDataValidator()
    normalized_jobs = []
    
    for job in jobs:
        normalized = validator.normalize_job(job)
        if normalized:
            normalized_jobs.append(normalized)
    
    logger.info(f"Validated {len(normalized_jobs)} out of {len(jobs)} jobs")
    return normalized_jobs
