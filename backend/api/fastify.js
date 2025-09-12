const fastify = require('fastify')({ logger: true });
const { createClient } = require('@supabase/supabase-js');

// Initialize Supabase client
const supabaseUrl = process.env.SUPABASE_URL || 'your-supabase-url';
const supabaseKey = process.env.SUPABASE_KEY || 'your-supabase-key';
const supabase = createClient(supabaseUrl, supabaseKey);

// Register the plugin to make Supabase available in routes
fastify.register(async function (fastify, options) {
  fastify.decorate('supabase', supabase);
});

// GET /api/jobs - Return latest jobs from Supabase
fastify.get('/api/jobs', async (request, reply) => {
  try {
    const { data, error } = await supabase
      .from('jobs')
      .select('*')
      .order('date_posted', { ascending: false })
      .limit(20);
    
    if (error) {
      throw new Error(error.message);
    }
    
    return reply.send(data);
  } catch (error) {
    console.error('Error fetching jobs:', error);
    return reply.status(500).send({ error: 'Failed to fetch jobs' });
  }
});

// GET /api/search - Filter jobs by keyword
fastify.get('/api/search', async (request, reply) => {
  const { keyword } = request.query;
  
  if (!keyword) {
    return reply.status(400).send({ error: 'Keyword is required' });
  }
  
  try {
    const { data, error } = await supabase
      .from('jobs')
      .select('*')
      .ilike('title', `%${keyword}%`)
      .or(`company.ilike.%${keyword}%`)
      .order('date_posted', { ascending: false })
      .limit(20);
    
    if (error) {
      throw new Error(error.message);
    }
    
    return reply.send(data);
  } catch (error) {
    console.error('Error searching jobs:', error);
    return reply.status(500).send({ error: 'Failed to search jobs' });
  }
});

// Start the server
const start = async () => {
  try {
    await fastify.listen({ port: 3000 });
    console.log('Server running on http://localhost:3000');
  } catch (err) {
    console.error('Error starting server:', err);
    process.exit(1);
  }
};

start();
