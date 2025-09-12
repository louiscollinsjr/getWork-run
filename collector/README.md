# Job Collector (MVP)

This is a Python-based job collection system that scrapes job listings and stores them in Supabase.

## Architecture
- **Collector**: Python + JobSpy for scraping jobs from Indeed (primary source)
- **Storage**: Supabase database 
- **API**: Node.js Fastify server for frontend queries

## Configuration

### Supabase Setup
1. Create a Supabase project at https://supabase.com/
2. Create a `jobs` table with the following columns:
   - id (BIGSERIAL PRIMARY KEY)
   - title (text)
   - company (text)
   - location (text)
   - salary (text)
   - description (text)
   - url (text)
   - date_posted (timestamp)
   - job_type (text)
   - remote (boolean)
   - scraped_at (timestamp)

### Supabase RLS Configuration
1. Enable Row Level Security (RLS) on the jobs table
2. Set up appropriate policies for read/write access:
   - Allow all users to read jobs (public read access)
   - Allow authenticated users to insert jobs 
   - Allow authenticated users to update jobs
   - Allow service role to delete jobs

### SQL Setup Script
You can use the provided SQL script to set up the table and policies:
```sql
-- Create jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary TEXT,
    description TEXT,
    url TEXT,
    date_posted TIMESTAMP WITH TIME ZONE,
    job_type TEXT,
    remote BOOLEAN DEFAULT FALSE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security (RLS) on the jobs table
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Create policies for the jobs table
-- Allow all users to read jobs (public read access)
CREATE POLICY "Allow public read access" ON jobs FOR SELECT USING (true);

-- Allow authenticated users to insert jobs (service role and authenticated users)
CREATE POLICY "Allow authenticated insert access" ON jobs FOR INSERT WITH CHECK (true);

-- Allow authenticated users to update jobs
CREATE POLICY "Allow authenticated update access" ON jobs FOR UPDATE USING (true);

-- Allow service role to delete jobs
CREATE POLICY "Allow service role to delete jobs" ON jobs FOR DELETE USING (true);
```

### Environment Variables
The collector uses the following environment variables from `.env`:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase service role key (or API key/anon key)

## Running the Collector

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the collector to scrape and store jobs:
```bash
python collector.py
```

Or using the helper script:
```bash
./run.sh
```

## Additional Scripts

Three additional scripts have been created to process job data:

1. `normalize_jobs.py` - Process jobs where core_skills is NULL using OpenAI to extract skills and experience information
2. `embed_jobs.py` - Generate embeddings for jobs using OpenAI Batch API in batches of 500
3. `process_batches.py` - Handle OpenAI batch job status polling and update job embeddings

These scripts can be run independently or as part of a pipeline:
```bash
python normalize_jobs.py
python embed_jobs.py
python process_batches.py
```

## Running the API Server

1. Install dependencies:
```bash
cd backend && npm install
```

2. Run the Fastify API server:
```bash
cd backend && node api/fastify.js
```

The API will be available at http://localhost:3000

## API Endpoints
- `GET /api/jobs` - Return latest jobs from Supabase
- `GET /api/search?keyword=...` - Filter jobs by keyword

## Windsurfer Integration
To run this in Windsurfer environment:
1. Run the collector script to collect jobs: `python collector.py`
2. Run the API server: `node backend/api/fastify.js` 
3. The API will serve job data to frontend applications

## Testing
You can test the API using curl:
```bash
curl http://localhost:3000/api/jobs
curl "http://localhost:3000/api/search?keyword=software"
