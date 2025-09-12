import sys
print(f"Using Python executable: {sys.executable}")
print(f"Python executable path: {sys.executable}")

import os
import sys
import math
from datetime import datetime, date
from typing import List
from jobspy import scrape_jobs
from supabase import create_client, Client
import csv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_API_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# We'll use the Job class from jobspy directly

def job_to_dict(job) -> dict:
    # Convert NaN values to None and handle various data types
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
    
    job_dict = {
        "title": clean_value(getattr(job, 'title', None)),
        "company": clean_value(getattr(job, 'company', None)),
        "location": clean_value(getattr(job, 'location', None)),
        "salary": clean_value(getattr(job, 'salary', None)),
        "description": clean_value(getattr(job, 'description', None)),
        "job_url": clean_value(getattr(job, 'job_url', None)) or clean_value(getattr(job, 'url', None)),
        "date_posted": date_posted_str,
        "job_type": clean_value(getattr(job, 'job_type', None)),
        "remote": bool(getattr(job, 'remote', False)) if getattr(job, 'remote', None) is not None else False
    }
    return job_dict

def insert_jobs(jobs):
    for job in jobs:
        job_dict = job_to_dict(job)
        try:
            # Check for existing job by title and company
            existing_job = supabase.table("jobs").select("id").eq("title", job_dict["title"]).eq("company", job_dict["company"]).execute()
            
            if existing_job.data:
                # Update existing job
                job_id = existing_job.data[0]['id']
                supabase.table("jobs").update(job_dict).eq("id", job_id).execute()
                print(f"Updated job: {job_dict['title']} at {job_dict['company']}")
            else:
                # Insert new job
                supabase.table("jobs").insert(job_dict).execute()
                print(f"Inserted job: {job_dict['title']} at {job_dict['company']}")
        except Exception as e:
            print(f"Error inserting job: {e}")
            print(f"Skipping job: {job_dict['title']} at {job_dict['company']}")

def collect_jobs():
    """Collect jobs using JobSpy and store them in Supabase"""
    print("Starting job collection...")
    
    # Scrape jobs from Indeed (as recommended by jobspy creators)
    jobs = scrape_jobs(
        site_name=["indeed"], # Using Indeed as primary source (best scraper with no rate limiting)
        search_term="software engineer",
        google_search_term="software engineer jobs near San Francisco, CA since yesterday",
        location="San Francisco, CA",
        results_wanted=20,
        hours_old=72,
        country_indeed='USA',
        # linkedin_fetch_description=True # gets more info such as description, direct job url (slower)
        # proxies=["208.195.175.46:65095", "208.195.175.45:65095", "localhost"],
    )
    
    if jobs is None or len(jobs) == 0:
        print("No jobs found")
        return
    
    # Convert DataFrame rows to job objects that we can process
    jobs_list = []
    for _, job_row in jobs.iterrows():
        # Create a simple object from the pandas row
        job_obj = type('Job', (), {})()
        for key, value in job_row.items():
            setattr(job_obj, key, value)
        jobs_list.append(job_obj)
    
    insert_jobs(jobs_list)

    # Optional: Save to CSV for debugging (as shown in the example)
    try:
        jobs.to_csv("jobs.csv", quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
    except Exception as e:
        print(f"Warning: Could not save jobs to CSV: {e}")

if __name__ == "__main__":
    collect_jobs()
