-- Add salary parsing columns to jobs table
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS salary_min INTEGER,
ADD COLUMN IF NOT EXISTS salary_max INTEGER,
ADD COLUMN IF NOT EXISTS salary_currency VARCHAR(5) DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS salary_period VARCHAR(20) DEFAULT 'year', -- 'year', 'month', 'hour', 'week', 'per year', etc.
ADD COLUMN IF NOT EXISTS salary_type VARCHAR(25); -- 'range', 'starting', 'negotiable', 'not_specified'

-- Add embedding text column for comprehensive job matching
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS embedding_text TEXT;

-- Fix VARCHAR length issues for salary fields
ALTER TABLE jobs ALTER COLUMN salary_period TYPE VARCHAR(20);
ALTER TABLE jobs ALTER COLUMN salary_type TYPE VARCHAR(25);
ALTER TABLE jobs ALTER COLUMN salary_currency TYPE VARCHAR(5);
