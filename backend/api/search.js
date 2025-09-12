require('dotenv').config();
const fastify = require('fastify')({ logger: true });
const { createClient } = require('@supabase/supabase-js');
const { OpenAI } = require('openai');

// Validate environment variables
if (!process.env.SUPABASE_URL || !process.env.SUPABASE_KEY) {
  throw new Error('Supabase credentials missing in environment variables');
}

// Initialize clients
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_KEY || process.env.SUPABASE_SERVICE_KEY
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
    
    // Format response
    const formattedResults = results.map(job => ({
      job_id: job.id,
      title: job.title,
      company: job.company,
      similarity: job.similarity,
      match_reasoning: `Matches ${query} based on core requirements`
    }));

    return { results: formattedResults };
    
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
