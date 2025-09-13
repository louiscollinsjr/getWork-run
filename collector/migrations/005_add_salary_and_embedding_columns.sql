-- Add salary parsing columns to jobs table
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS salary_min INTEGER,
ADD COLUMN IF NOT EXISTS salary_max INTEGER,
ADD COLUMN IF NOT EXISTS salary_currency VARCHAR(3) DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS salary_period VARCHAR(10) DEFAULT 'year', -- 'year', 'month', 'hour', 'week'
ADD COLUMN IF NOT EXISTS salary_type VARCHAR(20); -- 'range', 'starting', 'negotiable', 'not_specified'

-- Add embedding text column for comprehensive job matching
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS embedding_text TEXT;

-- Create indexes for salary queries
CREATE INDEX IF NOT EXISTS idx_jobs_salary_min ON jobs(salary_min);
CREATE INDEX IF NOT EXISTS idx_jobs_salary_max ON jobs(salary_max);
CREATE INDEX IF NOT EXISTS idx_jobs_salary_type ON jobs(salary_type);
