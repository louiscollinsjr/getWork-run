-- Database schema updates for enhanced job collection system
-- Run these updates on your Supabase database

-- 1. Update jobs table to handle null companies gracefully
ALTER TABLE jobs ALTER COLUMN company DROP NOT NULL;
ALTER TABLE jobs ALTER COLUMN company SET DEFAULT 'Unknown Company';

-- 2. Add collection metadata columns
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS batch_id TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS search_term_used TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS location_searched TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS collection_strategy TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_site TEXT;

-- 3. Create quota tracking table
CREATE TABLE IF NOT EXISTS quota_tracking (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    batch_id TEXT NOT NULL,
    site_usage JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(date, batch_id)
);

-- 4. Create collection statistics table
CREATE TABLE IF NOT EXISTS collection_stats (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_jobs_collected INTEGER DEFAULT 0,
    jobs_by_site JSONB DEFAULT '{}',
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    avg_jobs_per_search DECIMAL(8,2) DEFAULT 0.0,
    top_search_terms JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_source_site ON jobs(source_site);
CREATE INDEX IF NOT EXISTS idx_jobs_search_term ON jobs(search_term_used);
CREATE INDEX IF NOT EXISTS idx_jobs_collection_date ON jobs(collected_at);
CREATE INDEX IF NOT EXISTS idx_jobs_company_location ON jobs(company, city, state);

-- 6. Create function to remove duplicate jobs
CREATE OR REPLACE FUNCTION remove_duplicate_jobs()
RETURNS INTEGER AS $$
DECLARE
    duplicates_removed INTEGER;
BEGIN
    -- Remove duplicates based on job_url_hash, keeping the most recent
    WITH duplicates AS (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY job_url_hash 
                   ORDER BY collected_at DESC, created_at DESC
               ) as rn
        FROM jobs
        WHERE job_url_hash IS NOT NULL
    )
    DELETE FROM jobs 
    WHERE id IN (
        SELECT id FROM duplicates WHERE rn > 1
    );
    
    GET DIAGNOSTICS duplicates_removed = ROW_COUNT;
    
    RETURN duplicates_removed;
END;
$$ LANGUAGE plpgsql;

-- 7. Create function to update collection statistics
CREATE OR REPLACE FUNCTION update_collection_stats()
RETURNS JSONB AS $$
DECLARE
    today_date DATE := CURRENT_DATE;
    stats_result JSONB;
BEGIN
    -- Calculate today's statistics
    WITH daily_stats AS (
        SELECT 
            COUNT(*) as total_jobs,
            COUNT(DISTINCT source_site) as sites_used,
            ROUND(AVG(CASE WHEN company != 'Unknown Company' THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate,
            json_object_agg(COALESCE(source_site, 'unknown'), site_count) as jobs_by_site,
            json_agg(search_term_data) as top_terms
        FROM jobs j
        LEFT JOIN (
            SELECT source_site, COUNT(*) as site_count
            FROM jobs 
            WHERE DATE(collected_at) = today_date
            GROUP BY source_site
        ) site_counts ON j.source_site = site_counts.source_site
        LEFT JOIN (
            SELECT search_term_used, COUNT(*) as term_count
            FROM jobs 
            WHERE DATE(collected_at) = today_date 
            AND search_term_used IS NOT NULL
            GROUP BY search_term_used
            ORDER BY term_count DESC
            LIMIT 10
        ) term_stats ON j.search_term_used = term_stats.search_term_used
        CROSS JOIN LATERAL (
            SELECT json_build_object('term', term_stats.search_term_used, 'count', term_stats.term_count) as search_term_data
        ) term_data
        WHERE DATE(j.collected_at) = today_date
    )
    INSERT INTO collection_stats (
        date, total_jobs_collected, jobs_by_site, success_rate, top_search_terms
    ) 
    SELECT 
        today_date,
        total_jobs,
        jobs_by_site,
        success_rate,
        top_terms
    FROM daily_stats
    ON CONFLICT (date) DO UPDATE SET
        total_jobs_collected = EXCLUDED.total_jobs_collected,
        jobs_by_site = EXCLUDED.jobs_by_site,
        success_rate = EXCLUDED.success_rate,
        top_search_terms = EXCLUDED.top_search_terms,
        updated_at = NOW();
    
    -- Return the updated statistics
    SELECT row_to_json(cs) INTO stats_result
    FROM collection_stats cs
    WHERE date = today_date;
    
    RETURN stats_result;
END;
$$ LANGUAGE plpgsql;

-- 8. Create view for job collection dashboard
CREATE OR REPLACE VIEW job_collection_dashboard AS
SELECT 
    DATE(collected_at) as collection_date,
    COUNT(*) as total_jobs,
    COUNT(DISTINCT company) as unique_companies,
    COUNT(DISTINCT CONCAT(city, ', ', state)) as unique_locations,
    COUNT(CASE WHEN company = 'Unknown Company' THEN 1 END) as jobs_missing_company,
    ROUND(
        (COUNT(*) - COUNT(CASE WHEN company = 'Unknown Company' THEN 1 END)) * 100.0 / COUNT(*), 
        2
    ) as data_quality_score,
    json_object_agg(
        COALESCE(source_site, 'unknown'), 
        site_job_count
    ) as jobs_by_site
FROM jobs j
LEFT JOIN (
    SELECT 
        source_site,
        DATE(collected_at) as date,
        COUNT(*) as site_job_count
    FROM jobs
    GROUP BY source_site, DATE(collected_at)
) site_stats ON j.source_site = site_stats.source_site 
    AND DATE(j.collected_at) = site_stats.date
WHERE collected_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(collected_at)
ORDER BY collection_date DESC;

-- 9. Create alerts for monitoring
CREATE TABLE IF NOT EXISTS collection_alerts (
    id SERIAL PRIMARY KEY,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    metadata JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- 10. Create function to check for collection issues
CREATE OR REPLACE FUNCTION check_collection_health()
RETURNS TABLE(alert_type TEXT, message TEXT, severity TEXT) AS $$
BEGIN
    -- Check if daily collection is below threshold
    IF (SELECT COUNT(*) FROM jobs WHERE DATE(collected_at) = CURRENT_DATE) < 100 THEN
        RETURN QUERY SELECT 
            'low_collection'::TEXT, 
            'Daily job collection is below expected threshold'::TEXT,
            'warning'::TEXT;
    END IF;
    
    -- Check if too many jobs are missing company data
    IF (SELECT 
            COUNT(CASE WHEN company = 'Unknown Company' THEN 1 END) * 100.0 / COUNT(*)
        FROM jobs 
        WHERE DATE(collected_at) = CURRENT_DATE
       ) > 30 THEN
        RETURN QUERY SELECT 
            'high_missing_data'::TEXT,
            'More than 30% of jobs are missing company information'::TEXT,
            'error'::TEXT;
    END IF;
    
    -- Check if no jobs collected in last 6 hours
    IF NOT EXISTS (
        SELECT 1 FROM jobs 
        WHERE collected_at > NOW() - INTERVAL '6 hours'
    ) THEN
        RETURN QUERY SELECT 
            'collection_stopped'::TEXT,
            'No jobs collected in the last 6 hours'::TEXT,
            'critical'::TEXT;
    END IF;
    
    RETURN;
END;
$$ LANGUAGE plpgsql;
