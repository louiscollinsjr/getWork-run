// Only load dotenv in development
if (process.env.NODE_ENV !== 'production') {
  require('dotenv').config();
}

const fastify = require('fastify')({ logger: true });
const { createClient } = require('@supabase/supabase-js');
const { OpenAI } = require('openai');

// Register CORS plugin for React Native development
fastify.register(require('@fastify/cors'), {
  origin: true, // Allow all origins during development
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
});

// Debug environment variables
console.log('Environment variables check:');
console.log('NODE_ENV:', process.env.NODE_ENV || 'undefined');
console.log('SUPABASE_URL:', process.env.SUPABASE_URL ? 'SET' : 'MISSING');
console.log('SUPABASE_SERVICE_KEY:', process.env.SUPABASE_SERVICE_KEY ? 'SET' : 'MISSING');
console.log('OPENAI_API_KEY:', process.env.OPENAI_API_KEY ? 'SET' : 'MISSING');

// Validate environment variables
if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY) {
  console.error('Missing environment variables:');
  console.error('SUPABASE_URL:', process.env.SUPABASE_URL ? 'OK' : 'MISSING');
  console.error('SUPABASE_SERVICE_KEY:', process.env.SUPABASE_SERVICE_KEY ? 'OK' : 'MISSING');
  throw new Error('Supabase credentials missing in environment variables');
}

// Initialize clients
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

/**
 * Generate embedding vector for search query
 */
async function getQueryEmbedding(query) {
  try {
    const response = await openai.embeddings.create({
      model: 'text-embedding-3-small',
      input: query
    });
    return response.data[0].embedding;
  } catch (error) {
    console.error('Embedding generation error:', error);
    throw error;
  }
}

/**
 * Perform vector search with filters
 */
async function vectorSearch(embedding, filters = {}) {
  try {
    const { data, error } = await supabase.rpc('weighted_vector_search', {
      query_embedding: embedding,
      match_count: 20,
      filter_location: filters.location,
      filter_job_type: filters.job_type,
      filter_company: filters.company
    });

    if (error) throw error;
    return data;
  } catch (error) {
    console.error('Vector search error:', error);
    throw error;
  }
}

// GET /api/health - Health check endpoint
fastify.get('/api/health', async (request, reply) => {
  return {
    status: 'ok',
    timestamp: new Date().toISOString(),
    message: 'GetWork API is running!',
    endpoints: {
      search: 'POST /api/search - Natural language job search',
      jobs: 'GET /api/jobs - Get latest jobs'
    }
  };
});

// POST /api/search endpoint
fastify.post('/api/search', async (request, reply) => {
  try {
    const { query, filters = {} } = request.body;
    
    if (!query) {
      return reply.status(400).send({ error: 'Query is required' });
    }

    console.log(`Processing search for: ${query}`);
    
    // Generate embedding
    const embedding = await getQueryEmbedding(query);
    
    // Perform vector search
    const results = await vectorSearch(embedding, filters);
    
    // Return results
    return {
      results: results.map(job => ({
        id: job.id,
        title: job.title,
        company: job.company,
        location: job.location,
        job_url: job.job_url || '',
        core_skills: job.core_skills,
        nice_to_have_skills: job.nice_to_have_skills,
        realistic_experience_level: job.realistic_experience_level,
        transferable_skills_indicators: job.transferable_skills_indicators,
        actual_job_complexity: job.actual_job_complexity,
        bias_removal_notes: job.bias_removal_notes,
        processed_at: job.processed_at,
        similarity: job.similarity
      }))
    };
    
  } catch (error) {
    console.error('Search error:', error);
    return reply.status(500).send({ 
      error: 'Search failed', 
      details: error.message 
    });
  }
});

// Start server
const start = async () => {
  try {
    await fastify.listen({ 
      port: process.env.PORT || 3000,
      host: '0.0.0.0' 
    });
    console.log(`Server running on ${fastify.server.address().port}`);
  } catch (err) {
    console.error('Server error:', err);
    process.exit(1);
  }
};

start();
