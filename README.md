# GetWork - Conversational Job Search App

A React Native mobile app with a Node.js backend that enables natural language job search using vector embeddings and AI-powered matching.

## Architecture

- **Frontend**: React Native (Expo) - `/Users/louiscollins/CascadeProjects/conversational-jobs`
- **Backend**: Node.js (Fastify) with Supabase - `backend/`
- **Database**: Supabase (PostgreSQL with pgvector extension)
- **AI**: OpenAI embeddings for semantic search

## Setup Instructions

### 1. Backend Setup

```bash
cd backend
npm install
```

Create a `.env` file in the `backend` directory:
```env
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_KEY=your-supabase-service-key
OPENAI_API_KEY=your-openai-api-key
NODE_ENV=development
```

### 2. Database Setup

Run the SQL setup file in your Supabase dashboard:
```bash
# Execute the contents of collector/supabase_setup.sql in your Supabase SQL editor
```

This will:
- Enable the pgvector extension
- Create the jobs table with all required columns
- Set up vector search indexes
- Create the weighted_vector_search function

### 3. Frontend Setup

```bash
cd /Users/louiscollins/CascadeProjects/conversational-jobs
npm install
```

## Running the Application

### Start the Backend
```bash
cd backend
npm run dev  # For development with auto-reload
# or
npm start    # For production
```

The backend will start on `http://localhost:3000`

### Start the Frontend
```bash
cd /Users/louiscollins/CascadeProjects/conversational-jobs
npm start
```

Then use the Expo Go app to scan the QR code or run on simulator.

## Features

### Current Features
- ✅ Natural language job search using OpenAI embeddings
- ✅ Vector similarity search with Supabase
- ✅ Real-time chat interface
- ✅ Job cards with similarity scores
- ✅ Animated UI matching inspiration video
- ✅ Error handling and loading states

### API Endpoints

- `POST /api/search` - Natural language job search
  ```json
  {
    "query": "React Native developer with TypeScript experience",
    "filters": {
      "location": "San Francisco",
      "job_type": "Full-time",
      "company": "TechCorp"
    }
  }
  ```

- `GET /api/jobs` - Get latest jobs

## Database Schema

The jobs table includes:
- Basic job info (title, company, location, salary)
- AI-extracted fields (core_skills, experience_level, etc.)
- Vector embeddings for semantic search
- Salary parsing (min, max, currency, period)

## Development

### Adding New Features
1. Backend changes go in `backend/api/`
2. Frontend changes go in the React Native app
3. Database migrations in `collector/migrations/`

### Troubleshooting

**App crashes during chat:**
- Fixed animation issues that were causing crashes
- Added proper error handling for API calls
- Added loading states

**No search results:**
- Ensure backend is running on port 3000
- Check environment variables are set
- Verify Supabase connection
- Make sure jobs have embeddings generated

**CORS issues:**
- Backend now includes CORS headers for React Native development

## Tech Stack

- **Frontend**: React Native, Expo, React Native Reanimated, Gifted Chat
- **Backend**: Node.js, Fastify, Supabase SDK
- **Database**: PostgreSQL with pgvector extension
- **AI**: OpenAI embeddings (text-embedding-3-small)
- **Deployment**: Vercel (planned), Expo EAS (planned)
