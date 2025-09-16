-- Enable pgvector extension for vector search
CREATE EXTENSION IF NOT EXISTS vector;

-- Create jobs table with full schema
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary TEXT,
    description TEXT,
    url TEXT,
    job_url TEXT,
    date_posted TIMESTAMP WITH TIME ZONE,
    job_type TEXT,
    remote BOOLEAN DEFAULT FALSE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Salary parsing columns
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency VARCHAR(5) DEFAULT 'USD',
    salary_period VARCHAR(20) DEFAULT 'year',
    salary_type VARCHAR(25),
    
    -- AI-extracted job normalization fields
    core_skills TEXT[],
    nice_to_have_skills TEXT[],
    realistic_experience_level TEXT,
    transferable_skills_indicators TEXT[],
    actual_job_complexity TEXT,
    bias_removal_notes TEXT,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Embedding fields
    embedding_text TEXT,
    embedding vector(1536)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_remote ON jobs(remote);
CREATE INDEX IF NOT EXISTS idx_jobs_processed_at ON jobs(processed_at);

-- Create vector similarity search index
CREATE INDEX IF NOT EXISTS idx_jobs_embedding ON jobs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

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

-- Create weighted vector search function
CREATE OR REPLACE FUNCTION weighted_vector_search(
    query_embedding vector(1536),
    match_count int DEFAULT 20,
    filter_location text DEFAULT NULL,
    filter_job_type text DEFAULT NULL,
    filter_company text DEFAULT NULL
)
RETURNS TABLE (
    id bigint,
    title text,
    company text,
    location text,
    job_url text,
    core_skills text[],
    nice_to_have_skills text[],
    realistic_experience_level text,
    transferable_skills_indicators text[],
    actual_job_complexity text,
    bias_removal_notes text,
    processed_at timestamp with time zone,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        j.id,
        j.title,
        j.company,
        j.location,
        j.job_url,
        j.core_skills,
        j.nice_to_have_skills,
        j.realistic_experience_level,
        j.transferable_skills_indicators,
        j.actual_job_complexity,
        j.bias_removal_notes,
        j.processed_at,
        (1 - (j.embedding <=> query_embedding)) as similarity
    FROM jobs j
    WHERE j.embedding IS NOT NULL
        AND (filter_location IS NULL OR j.location ILIKE '%' || filter_location || '%')
        AND (filter_job_type IS NULL OR j.job_type ILIKE '%' || filter_job_type || '%')
        AND (filter_company IS NULL OR j.company ILIKE '%' || filter_company || '%')
    ORDER BY j.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
