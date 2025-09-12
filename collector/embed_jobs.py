#!/usr/bin/env python3
"""
Generate embeddings for jobs using OpenAI Batch API.
This script processes jobs with NULL embeddings in batches of 500.
"""

import os
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
        logging.FileHandler('embed_jobs.log'),
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

def get_jobs_without_embeddings(batch_size: int = 500) -> List[Dict]:
    """Query jobs with NULL embeddings in batches"""
    try:
        response = supabase.table("jobs").select("*").is_null("embeddings").limit(batch_size).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error querying jobs: {e}")
        return []

def create_jsonl_content(jobs: List[Dict]) -> str:
    """Generate JSONL content for OpenAI batch requests"""
    jsonl_lines = []
    
    for i, job in enumerate(jobs):
        # Prepare the content for embedding
        core_requirements = job.get("description", "") or ""
        transferable_context = job.get("title", "") or ""
        role_context = job.get("company", "") or ""
        full_description = f"Title: {job.get('title', '')}\nCompany: {job.get('company', '')}\nDescription: {core_requirements}"
        
        # Create the OpenAI batch request payload
        payload = {
            "custom_id": str(job.get("id", i)),
            "method": "POST",
            "url": "/v1/embeddings",
            "body": {
                "input": [
                    core_requirements,
                    transferable_context,
                    role_context,
                    full_description
                ],
                "model": "text-embedding-3-small"
            }
        }
        
        jsonl_lines.append(json.dumps(payload))
    
    return "\n".join(jsonl_lines)

def submit_batch_job(jsonl_content: str) -> str:
    """Submit JSONL content to OpenAI Batch API"""
    try:
        # Create the batch job
        batch_job = openai_client.batches.create(
            input_file_id=openai_client.files.create(
                file=jsonl_content.encode('utf-8'),
                purpose="batch"
            ).id,
            endpoint="/v1/embeddings",
            completion_window="24h"
        )
        
        return batch_job.id
    except Exception as e:
        logger.error(f"Error submitting batch job: {e}")
        return None

def insert_batch_job_record(batch_id: str, job_count: int) -> bool:
    """Insert a row into batch_jobs table"""
    try:
        batch_data = {
            "batch_id": batch_id,
            "status": "submitted",
            "job_count": job_count,
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase.table("batch_jobs").insert(batch_data).execute()
        
        if response.data:
            logger.info(f"Successfully inserted batch job record for {batch_id}")
            return True
        else:
            logger.error(f"Failed to insert batch job record for {batch_id}: No data returned")
            return False
            
    except Exception as e:
        logger.error(f"Error inserting batch job record: {e}")
        return False

def main():
    """Main function to process jobs and create embeddings"""
    logger.info("Starting embed_jobs.py")
    
    # Get jobs without embeddings (max 500 at a time)
    jobs = get_jobs_without_embeddings(500)
    
    if not jobs:
        logger.info("No jobs found to process")
        return
    
    logger.info(f"Found {len(jobs)} jobs to process")
    
    # Create JSONL content for OpenAI batch
    jsonl_content = create_jsonl_content(jobs)
    
    # Submit to OpenAI Batch API
    batch_id = submit_batch_job(jsonl_content)
    
    if not batch_id:
        logger.error("Failed to submit batch job to OpenAI")
        return
    
    logger.info(f"Successfully submitted batch job: {batch_id}")
    
    # Insert record into batch_jobs table
    success = insert_batch_job_record(batch_id, len(jobs))
    
    if success:
        logger.info(f"Successfully created batch job record for {batch_id}")
    else:
        logger.error(f"Failed to create batch job record for {batch_id}")

if __name__ == "__main__":
    main()
