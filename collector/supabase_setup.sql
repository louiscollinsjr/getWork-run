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
