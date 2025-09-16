#!/bin/bash

echo "🚀 Starting GetWork Backend Server"
echo "=================================="

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo "❌ Backend .env file not found!"
    echo "Please copy backend/.env.example to backend/.env and fill in your credentials"
    exit 1
fi

# Navigate to backend directory
cd backend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing backend dependencies..."
    npm install
fi

echo "🔥 Starting backend server in development mode..."
echo "Server will be available at: http://localhost:3000"
echo ""
echo "API Endpoints:"
echo "  GET  /api/jobs - Get latest jobs"
echo "  POST /api/search - Search jobs with natural language"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

npm run dev
