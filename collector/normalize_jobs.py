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

def get_jobs_to_normalize() -> List[Dict]:
    """Query jobs that need normalization (core_skills IS NULL OR processed_at IS NULL)"""
    try:
        response = supabase.table("jobs").select("*").or_(
            "core_skills.is.null,processed_at.is.null"
        ).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error querying jobs: {e}")
        return []

def extract_comprehensive_job_data(job_data: Dict) -> Dict[str, Any]:
    """Send job data to OpenAI gpt-4o-mini and extract comprehensive job information"""
    
    # Prepare the prompt content
    job_description = job_data.get("description", "") or ""
    job_title = job_data.get("title", "") or ""
    company = job_data.get("company", "") or ""
    existing_salary = job_data.get("salary", "") or ""
    
    # Create the JSON schema for OpenAI response
    system_prompt = """
    You are an expert job analyst who extracts comprehensive information from job postings.
    
    Extract ALL of the following information from the job description:
    
    SKILLS & EXPERIENCE:
    - core_skills: List of essential technical skills required for this role
    - nice_to_have_skills: List of additional skills that would be beneficial but aren't required  
    - realistic_experience_level: What level of experience is realistic for this position ("Entry Level", "Mid Level", "Senior Level")
    - transferable_skills_indicators: List of indicators that suggest transferable skills
    - actual_job_complexity: Assessment of the job's technical complexity ("Beginner", "Intermediate", "Advanced")
    - bias_removal_notes: List of specific bias reduction recommendations (e.g., ["Avoid strict degree requirements", "Include accommodation language", "Use inclusive evaluation criteria"])
    
    SALARY INFORMATION:
    - salary_min: Minimum salary as integer (null if not specified)
    - salary_max: Maximum salary as integer (null if not specified)
    - salary_currency: Currency code (e.g., "USD", "EUR")
    - salary_period: Pay frequency ("year", "month", "hour", "week")
    - salary_type: Classification ("range", "starting", "negotiable", "not_specified")
    
    Format your response as a JSON object with these exact fields:
    {
      "core_skills": ["skill1", "skill2", ...],
      "nice_to_have_skills": ["skill1", "skill2", ...],
      "realistic_experience_level": "string",
      "transferable_skills_indicators": ["indicator1", "indicator2", ...],
      "actual_job_complexity": "string",
      "bias_removal_notes": ["recommendation1", "recommendation2", ...],
      "salary_min": integer or null,
      "salary_max": integer or null,
      "salary_currency": "string",
      "salary_period": "string",
      "salary_type": "string"
    }
    
    Only return the JSON object with no additional text.
    """
    
    user_prompt = f"""
    Job Title: {job_title}
    Company: {company}
    Existing Salary Info: {existing_salary}
    
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

def generate_embedding_text(extracted_data: Dict, job_data: Dict) -> str:
    """Generate comprehensive text for embeddings"""
    title = job_data.get("title", "")
    core_skills = extracted_data.get("core_skills", [])
    transferable_skills = extracted_data.get("transferable_skills_indicators", [])
    experience_level = extracted_data.get("realistic_experience_level", "")
    complexity = extracted_data.get("actual_job_complexity", "")
    
    # Create rich text for better embeddings
    embedding_text = f"""Title: {title}
Skills: {', '.join(core_skills) if core_skills else 'Not specified'}
Experience: {experience_level}
Complexity: {complexity}
Transferable: {', '.join(transferable_skills) if transferable_skills else 'Not specified'}"""
    
    return embedding_text

def update_job_comprehensive(job_id: int, extracted_data: Dict, job_data: Dict) -> bool:
    """Update job row with extracted skills, salary data, and embedding text"""
    try:
        # Generate embedding text
        embedding_text = generate_embedding_text(extracted_data, job_data)
        
        # Prepare the update data
        update_data = {
            "core_skills": extracted_data.get("core_skills"),
            "nice_to_have_skills": extracted_data.get("nice_to_have_skills"),
            "realistic_experience_level": extracted_data.get("realistic_experience_level"),
            "transferable_skills_indicators": extracted_data.get("transferable_skills_indicators"),
            "actual_job_complexity": extracted_data.get("actual_job_complexity"),
            "bias_removal_notes": extracted_data.get("bias_removal_notes"),
            "salary_min": extracted_data.get("salary_min"),
            "salary_max": extracted_data.get("salary_max"),
            "salary_currency": extracted_data.get("salary_currency", "USD"),
            "salary_period": extracted_data.get("salary_period", "year"),
            "salary_type": extracted_data.get("salary_type", "not_specified"),
            "embedding_text": embedding_text,
            "processed_at": datetime.now().isoformat()
        }
        
        # Update the job in Supabase
        response = supabase.table("jobs").update(update_data).eq("id", job_id).execute()
        
        if response.data:
            logger.info(f"Successfully updated job {job_id} with comprehensive data")
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
    
    # Get jobs that need normalization
    jobs = get_jobs_to_normalize()
    
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
            # Extract comprehensive job data with OpenAI
            extracted_data = extract_comprehensive_job_data(job)
            
            if extracted_data:
                # Update job with comprehensive data
                success = update_job_comprehensive(job_id, extracted_data, job)
                
                if success:
                    success_count += 1
                else:
                    error_count += 1
            else:
                logger.warning(f"Failed to extract data for job {job_id}")
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
