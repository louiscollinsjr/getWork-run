#!/usr/bin/env python3
"""
Process OpenAI batch jobs to update job embeddings.
This script polls OpenAI Batch API for status and handles results.
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
        logging.FileHandler('process_batches.log'),
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

def get_pending_batch_jobs() -> List[Dict]:
    """Query batch_jobs where status in ('submitted','in_progress')"""
    try:
        response = supabase.table("batch_jobs").select("*").in_("status", ["submitted", "in_progress"]).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error querying batch jobs: {e}")
        return []

def check_batch_status(batch_id: str) -> Dict[str, Any]:
    """Poll OpenAI Batch API for status"""
    try:
        batch = openai_client.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "status": batch.status,
            "error": batch.errors if hasattr(batch, 'errors') and batch.errors else None,
            "completed_at": batch.completed_at,
            "failed_at": batch.failed_at
        }
    except Exception as e:
        logger.error(f"Error checking batch status for {batch_id}: {e}")
        return None

def download_batch_results(batch_id: str) -> List[Dict]:
    """Download results from OpenAI Batch API"""
    try:
        # Get the batch results file
        batch = openai_client.batches.retrieve(batch_id)
        
        if not batch.output_file_id:
            logger.error(f"No output file found for batch {batch_id}")
            return []
        
        # Download the results file
        file_content = openai_client.files.content(batch.output_file_id)
        
        # Parse the JSONL content
        results = []
        for line in file_content.text.split('\n'):
            if line.strip():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSONL line: {e}")
        
        return results
    except Exception as e:
        logger.error(f"Error downloading batch results for {batch_id}: {e}")
        return []

def update_job_embeddings(job_id: int, embedding_data: Dict) -> bool:
    """Update job row with embedding data"""
    try:
        # Extract embeddings from the result
        response_body = embedding_data.get("response", {}).get("body", {})
        embeddings = response_body.get("data", [])
        
        # We expect 4 embeddings: core_requirements, transferable_context, role_context, full_description
        if len(embeddings) >= 3:
            core_embedding = embeddings[0].get("embedding", [])
            transferable_embedding = embeddings[1].get("embedding", [])
            role_embedding = embeddings[2].get("embedding", [])
            
            # Update the job in Supabase with all three embeddings
            update_data = {
                "core_requirements_embedding": core_embedding,
                "transferable_context_embedding": transferable_embedding,
                "role_context_embedding": role_embedding,
                "processed_at": datetime.now().isoformat()
            }
            
            response = supabase.table("jobs").update(update_data).eq("id", job_id).execute()
            
            if response.data:
                logger.info(f"Successfully updated embeddings for job {job_id}")
                return True
            else:
                logger.error(f"Failed to update embeddings for job {job_id}: No data returned")
                return False
        else:
            logger.warning(f"Insufficient embeddings found for job {job_id}: got {len(embeddings)}, expected 3+")
            return False
            
    except Exception as e:
        logger.error(f"Error updating job {job_id} with embeddings: {e}")
        return False

def update_batch_job_status(batch_id: str, status: str, processed_count: int = 0) -> bool:
    """Update batch_jobs table with new status and processed count"""
    try:
        update_data = {
            "status": status,
            "processed_count": processed_count,
            "completed_at": datetime.now().isoformat() if status == "completed" else None
        }
        
        response = supabase.table("batch_jobs").update(update_data).eq("batch_id", batch_id).execute()
        
        if response.data:
            logger.info(f"Successfully updated batch job {batch_id} status to {status}")
            return True
        else:
            logger.error(f"Failed to update batch job {batch_id}: No data returned")
            return False
            
    except Exception as e:
        logger.error(f"Error updating batch job {batch_id} status: {e}")
        return False

def main():
    """Main function to process pending batch jobs"""
    logger.info("Starting process_batches.py")
    
    # Get pending batch jobs
    batch_jobs = get_pending_batch_jobs()
    
    if not batch_jobs:
        logger.info("No pending batch jobs found")
        return
    
    logger.info(f"Found {len(batch_jobs)} pending batch jobs to process")
    
    # Process each batch job
    for batch_job in batch_jobs:
        batch_id = batch_job.get("batch_id")
        logger.info(f"Processing batch job {batch_id}")
        
        # Check the status of this batch
        status_info = check_batch_status(batch_id)
        
        if not status_info:
            logger.error(f"Failed to get status for batch {batch_id}")
            continue
            
        logger.info(f"Batch {batch_id} status: {status_info['status']}")
        
        if status_info["status"] == "completed":
            # Download results
            logger.info(f"Downloading results for batch {batch_id}")
            results = download_batch_results(batch_id)
            
            if not results:
                logger.warning(f"No results found for batch {batch_id}")
                update_batch_job_status(batch_id, "failed")
                continue
            
            # Update job embeddings with results
            processed_count = 0
            
            for result in results:
                # Extract job ID from custom_id (which was set to the job ID)
                job_id = int(result.get("custom_id", 0))
                
                if job_id:
                    success = update_job_embeddings(job_id, result)
                    if success:
                        processed_count += 1
                    else:
                        logger.error(f"Failed to update embedding for job {job_id}")
                else:
                    logger.warning(f"Invalid job ID in result: {result.get('custom_id', 'unknown')}")
            
            # Update batch job status
            update_batch_job_status(batch_id, "completed", processed_count)
            logger.info(f"Successfully completed batch {batch_id} with {processed_count} jobs processed")
            
        elif status_info["status"] == "failed":
            # Log error and update status
            error_message = status_info.get("error", "Unknown error")
            logger.error(f"Batch {batch_id} failed: {error_message}")
            
            update_batch_job_status(batch_id, "failed")
            
        elif status_info["status"] == "in_progress":
            # Batch is still processing, update status to in_progress if needed
            logger.info(f"Batch {batch_id} is still in progress")
            
        else:
            # Handle any other status
            logger.info(f"Batch {batch_id} has status: {status_info['status']}")
            
    logger.info("Processing complete")

if __name__ == "__main__":
    main()
