# Task Implementation Progress

## Overview
Implement 3 Python scripts for the getWork.run collector that handle job normalization, embedding generation, and batch processing.

## Scripts to Implement

### 1. normalize_jobs.py
- [x] Connect to Supabase using SUPABASE_URL + SUPABASE_SERVICE_KEY
- [x] Query jobs where core_skills IS NULL
- [x] For each job:
  - [x] Send one chat completion to OpenAI gpt-4o-mini with a JSON schema output
  - [x] Extract: core_skills, nice_to_have_skills, realistic_experience_level, transferable_skills_indicators, actual_job_complexity, bias_removal_notes
  - [x] Update row in Supabase with processed_at = now()
- [x] Rate-limit 1 req/sec, log failures, skip errors
- [x] Add logging
- [x] Add dotenv for config
- [x] Add error handling

### 2. embed_jobs.py
- [x] Query jobs with NULL embeddings in batches of 500
- [x] Generate JSONL file for embedding requests: core_requirements, transferable_context, role_context, full_description
- [x] Submit to OpenAI Batch API
- [x] Insert a row into `batch_jobs` with batch_id, status="submitted", job_count
- [x] Add logging
- [x] Add dotenv for config
- [x] Add error handling

### 3. process_batches.py
- [x] Query `batch_jobs` where status in ("submitted","in_progress")
- [x] Poll OpenAI Batch API for status
- [x] If completed:
  - [x] Download results
  - [x] Parse embeddings
  - [x] Update corresponding job rows
  - [x] Set processed_count and completed_at, mark status="completed"
- [x] If failed, set status="failed" and log error
- [x] Add logging
- [x] Add dotenv for config
- [x] Add error handling

## Configuration Files
- [x] Create .env file with required environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY)
- [x] Create requirements.txt with dependencies (supabase, openai, python-dotenv)

## Testing
- [ ] Create test scripts to verify functionality
- [ ] Verify all scripts can be run independently

## Documentation
- [ ] Update README.md with usage instructions for the 3 scripts
