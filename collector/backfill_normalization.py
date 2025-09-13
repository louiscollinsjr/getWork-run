#!/usr/bin/env python3
"""
Backfill normalization for all existing jobs.
This script processes ALL jobs to populate missing normalized fields.
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
        logging.FileHandler('backfill_normalization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize clients
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")
openai_client = OpenAI(api_key=openai_api_key)

def get_jobs_to_normalize(batch_size: int = 50, offset: int = 0) -> List[Dict]:
    """Get jobs that need normalization (core_skills IS NULL OR processed_at IS NULL)"""
    try:
        response = supabase.table("jobs").select("*").or_(
            "core_skills.is.null,processed_at.is.null"
        ).range(offset, offset + batch_size - 1).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error querying jobs: {e}")
        return []

def extract_comprehensive_job_data(job_data: Dict) -> Dict[str, Any]:
    """Extract both skills and salary information using GPT-4o-mini"""
    
    job_description = job_data.get("description", "") or ""
    job_title = job_data.get("title", "") or ""
    company = job_data.get("company", "") or ""
    existing_salary = job_data.get("salary", "") or ""
    
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
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        logger.error(f"Error extracting data for job {job_data.get('id', 'unknown')}: {e}")
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
    """Update job with all extracted data"""
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
        
        response = supabase.table("jobs").update(update_data).eq("id", job_id).execute()
        
        if response.data:
            logger.info(f"✅ Updated job {job_id}")
            return True
        else:
            logger.error(f"❌ Failed to update job {job_id}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error updating job {job_id}: {e}")
        return False

def main():
    """Main backfill function"""
    logger.info("🚀 Starting comprehensive job normalization backfill")
    
    batch_size = 50
    offset = 0
    total_processed = 0
    success_count = 0
    error_count = 0
    
    while True:
        # Get batch of jobs
        jobs = get_jobs_to_normalize(batch_size, offset)
        
        if not jobs:
            logger.info("✅ No more jobs to process")
            break
            
        logger.info(f"📦 Processing batch: {len(jobs)} jobs (offset: {offset})")
        
        for i, job in enumerate(jobs):
            job_id = job.get("id")
            
            try:
                # Extract comprehensive data
                extracted_data = extract_comprehensive_job_data(job)
                
                if extracted_data:
                    success = update_job_comprehensive(job_id, extracted_data, job)
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                else:
                    logger.warning(f"⚠️  Failed to extract data for job {job_id}")
                    error_count += 1
                    
                total_processed += 1
                
                # Progress logging
                if total_processed % 10 == 0:
                    logger.info(f"📊 Progress: {total_processed} processed, {success_count} success, {error_count} errors")
                
            except Exception as e:
                logger.error(f"❌ Error processing job {job_id}: {e}")
                error_count += 1
                total_processed += 1
            
            # Rate limiting - 1 request per second
            time.sleep(1)
        
        offset += batch_size
    
    logger.info("🎉 Backfill complete!")
    logger.info(f"📊 Final stats: {total_processed} total, {success_count} success, {error_count} errors")

if __name__ == "__main__":
    main()
