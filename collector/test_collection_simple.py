#!/usr/bin/env python3
"""
Simple test script for European users or when some sites are blocked
"""

import sys
import os
from jobspy import scrape_jobs
from data_validator import validate_job_batch

def test_simple_collection():
    print("🧪 Testing Simple Job Collection (EU-friendly)")
    print("=" * 50)
    
    # Test sites that work well in Europe
    sites_to_test = ['indeed', 'linkedin']
    
    for site in sites_to_test:
        print(f"\n🔍 Testing {site}...")
        
        try:
            # Simple jobspy call
            jobs = scrape_jobs(
                site_name=[site],
                search_term="software engineer",
                location="Remote",
                results_wanted=3,
                hours_old=72,
                verbose=1
            )
            
            if jobs is not None and not jobs.empty:
                print(f"✅ {site}: Successfully collected {len(jobs)} jobs")
                
                # Test validation
                jobs_list = jobs.to_dict('records')
                validated = validate_job_batch(jobs_list)
                print(f"✅ {site}: Successfully validated {len(validated)} jobs")
                
                # Show sample
                if validated:
                    sample = validated[0]
                    print(f"📋 Sample: '{sample.get('title', 'N/A')}' at '{sample.get('company', 'N/A')}'")
            else:
                print(f"⚠️  {site}: No jobs found (normal for small test)")
                
        except Exception as e:
            print(f"❌ {site}: Error - {str(e)}")
    
    print("\n🎉 Simple test completed!")
    print("\nIf this works, you can deploy to GitHub Actions for full collection!")

if __name__ == "__main__":
    test_simple_collection()
