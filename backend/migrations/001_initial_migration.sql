-- Migration: Initial schema for getWork.run MVP

-- Update jobs table with new columns
ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS core_skills TEXT[],
ADD COLUMN IF NOT EXISTS nice_to_have_skills TEXT[],
ADD COLUMN IF NOT EXISTS realistic_experience_level TEXT,
ADD COLUMN IF NOT EXISTS transferable_skills_indicators TEXT[],
ADD COLUMN IF NOT EXISTS actual_job_complexity TEXT,
ADD COLUMN IF NOT EXISTS bias_removal_notes TEXT[],
ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS core_requirements_embedding VECTOR(1536),
ADD COLUMN IF NOT EXISTS transferable_context_embedding VECTOR(1536),
ADD COLUMN IF NOT EXISTS role_context_embedding VECTOR(1536);

-- Create batch_jobs table
CREATE TABLE IF NOT EXISTS batch_jobs (
    id BIGSERIAL PRIMARY KEY,
    batch_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    job_count INT,
    processed_count INT,
    created_at TIMESTAMP DEFAULT now(),
    completed_at TIMESTAMP
);

-- Enable RLS on jobs table
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Enable RLS on batch_jobs table
ALTER TABLE batch_jobs ENABLE ROW LEVEL SECURITY;

-- Create policies for jobs table
CREATE POLICY "service_role_full_access" ON jobs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "authenticated_read_only" ON jobs FOR SELECT TO authenticated USING (true);

-- Create policies for batch_jobs table
CREATE POLICY "service_role_full_access" ON batch_jobs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "authenticated_read_only" ON batch_jobs FOR SELECT TO authenticated USING (true);

-- Create RPC function for weighted vector search
CREATE OR REPLACE FUNCTION weighted_vector_search(
  query_embedding VECTOR(1536),
  match_count INT DEFAULT 20,
  filter_location TEXT DEFAULT NULL,
  filter_job_type TEXT DEFAULT NULL,
  filter_company TEXT DEFAULT NULL
)
RETURNS TABLE (
  id BIGINT,
  title TEXT,
  company TEXT,
  location TEXT,
  job_url TEXT,
  core_skills TEXT[],
  nice_to_have_skills TEXT[],
  realistic_experience_level TEXT,
  transferable_skills_indicators TEXT[],
  actual_job_complexity TEXT,
  bias_removal_notes TEXT[],
  processed_at TIMESTAMP,
  core_requirements_embedding VECTOR(1536),
  transferable_context_embedding VECTOR(1536),
  role_context_embedding VECTOR(1536),
  similarity FLOAT
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
    j.core_requirements_embedding,
    j.transferable_context_embedding,
    j.role_context_embedding,
    1 - (j.core_requirements_embedding <=> query_embedding) AS similarity
  FROM jobs j
  WHERE (filter_location IS NULL OR j.location ILIKE filter_location)
    AND (filter_job_type IS NULL OR j.job_type = filter_job_type)
    AND (filter_company IS NULL OR j.company ILIKE filter_company)
    AND j.core_requirements_embedding IS NOT NULL
  ORDER BY j.core_requirements_embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Grant execute permissions on the function to authenticated users
GRANT EXECUTE ON FUNCTION weighted_vector_search(VECTOR(1536), INT, TEXT, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION weighted_vector_search(VECTOR(1536), INT, TEXT, TEXT, TEXT) TO service_role;
