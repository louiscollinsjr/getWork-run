#!/usr/bin/env python3
"""
Normalize jobs by extracting skills and experience information using OpenAI.
This script processes jobs where core_skills is NULL.
"""

import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('normalize_jobs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_API_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

openai_client = OpenAI(api_key=openai_api_key)

def get_jobs_without_core_skills() -> List[Dict]:
    """Query jobs where core_skills IS NULL"""
    try:
        response = supabase.table("jobs").select("*").is_null("core_skills").execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error querying jobs: {e}")
        return []

def extract_skills_with_openai(job_data: Dict) -> Dict[str, Any]:
    """Send job data to OpenAI gpt-4o-mini and extract skills information"""
    
    # Prepare the prompt content
    job_description = job_data.get("description", "") or ""
    job_title = job_data.get("title", "") or ""
    company = job_data.get("company", "") or ""
    
    # Create the JSON schema for OpenAI response
    system_prompt = """
    You are an expert job analyst who extracts technical skills and experience requirements from job postings.
    
    Extract the following information from the job description:
    - core_skills: List of essential technical skills required for this role
    - nice_to_have_skills: List of additional skills that would be beneficial but aren't required  
    - realistic_experience_level: What level of experience is realistic for this position (e.g., "Entry Level", "Mid Level", "Senior Level")
    - transferable_skills_indicators: List of indicators that suggest transferable skills (e.g., "Experience in X domain", "Previous work in Y field")
    - actual_job_complexity: Assessment of the job's technical complexity (e.g., "Beginner", "Intermediate", "Advanced")
    - bias_removal_notes: Notes about any potential biases in the job description that might be removed or mitigated
    
    Format your response as a JSON object with these exact fields, using the following structure:
    {
      "core_skills": ["skill1", "skill2", ...],
      "nice_to_have_skills": ["skill1", "skill2", ...],
      "realistic_experience_level": "string",
      "transferable_skills_indicators": ["indicator1", "indicator2", ...],
      "actual_job_complexity": "string",
      "bias_removal_notes": "string"
    }
    
    Only return the JSON object with no additional text or explanation.
    """
    
    user_prompt = f"""
    Job Title: {job_title}
    Company: {company}
    
    Job Description:
    {job_description}
    """
    
    try:
        # Make the OpenAI API call
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        logger.error(f"Error calling OpenAI API for job {job_data.get('id', 'unknown')}: {e}")
        return None

def update_job_with_skills(job_id: int, skills_data: Dict) -> bool:
    """Update job row with extracted skills and processed_at timestamp"""
    try:
        # Prepare the update data
        update_data = {
            "core_skills": skills_data.get("core_skills"),
            "nice_to_have_skills": skills_data.get("nice_to_have_skills"),
            "realistic_experience_level": skills_data.get("realistic_experience_level"),
            "transferable_skills_indicators": skills_data.get("transferable_skills_indicators"),
            "actual_job_complexity": skills_data.get("actual_job_complexity"),
            "bias_removal_notes": skills_data.get("bias_removal_notes"),
            "processed_at": datetime.now().isoformat()
        }
        
        # Update the job in Supabase
        response = supabase.table("jobs").update(update_data).eq("id", job_id).execute()
        
        if response.data:
            logger.info(f"Successfully updated job {job_id}")
            return True
        else:
            logger.error(f"Failed to update job {job_id}: No data returned")
            return False
            
    except Exception as e:
        logger.error(f"Error updating job {job_id}: {e}")
        return False

def main():
    """Main function to process jobs"""
    logger.info("Starting normalize_jobs.py")
    
    # Get jobs without core_skills
    jobs = get_jobs_without_core_skills()
    
    if not jobs:
        logger.info("No jobs found to process")
        return
    
    logger.info(f"Found {len(jobs)} jobs to process")
    
    # Process each job with rate limiting (1 req/sec)
    success_count = 0
    error_count = 0
    
    for i, job in enumerate(jobs):
        job_id = job.get("id")
        
        # Log progress
        if i % 10 == 0:
            logger.info(f"Processing job {i+1}/{len(jobs)} (ID: {job_id})")
        
        try:
            # Extract skills with OpenAI
            skills_data = extract_skills_with_openai(job)
            
            if skills_data:
                # Update job with extracted skills
                success = update_job_with_skills(job_id, skills_data)
                
                if success:
                    success_count += 1
                else:
                    error_count += 1
            else:
                logger.warning(f"Failed to extract skills for job {job_id}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            error_count += 1
        
        # Rate limiting - sleep for 1 second between requests
        if i < len(jobs) - 1:  # Don't sleep after the last job
            time.sleep(1)
    
    logger.info(f"Processing complete. Success: {success_count}, Errors: {error_count}")

if __name__ == "__main__":
    main()
