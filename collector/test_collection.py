#!/usr/bin/env python3
"""
Quick test script to verify the enhanced collection system
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from enhanced_collector import EnhancedJobCollector
from data_validator import validate_job_batch

def test_collection():
    print("🧪 Testing Enhanced Job Collection System")
    print("=" * 50)
    
    try:
        # Initialize collector
        collector = EnhancedJobCollector()
        
        # Test a small collection
        print("Testing small job collection...")
        jobs = collector.scrape_jobs_smart(
            search_term="software engineer",
            location="Remote",
            results_wanted=5,
            hours_old=72
        )
        
        if jobs:
            print(f"✅ Successfully collected {len(jobs)} jobs")
            
            # Test validation
            validated = validate_job_batch(jobs)
            print(f"✅ Successfully validated {len(validated)} jobs")
            
            # Show sample
            if validated:
                sample = validated[0]
                print(f"📋 Sample job: '{sample.get('title', 'N/A')}' at '{sample.get('company', 'N/A')}'")
        else:
            print("⚠️  No jobs collected - this might be normal depending on search criteria")
        
        # Show quota status
        quota_status = collector.get_quota_status()
        print("\n📊 Site Quota Status:")
        for site, status in quota_status.items():
            print(f"  {site}: {status['used']}/{status['limit']} used")
        
        print("\n🎉 Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_collection()
    sys.exit(0 if success else 1)
