#!/bin/bash

# Simple local setup for enhanced job collection
# This just prepares your local environment for testing

echo "🔧 Setting up local development environment"
echo "=========================================="

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade -r requirements.txt

# Create .env from template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env template..."
    cp .env.enhanced .env
    echo "📝 Please edit .env with your Supabase credentials"
fi

echo "✅ Local setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your Supabase URL and service key"
echo "2. Run 'python3 test_collection.py' to test"
echo "3. Commit and push to GitHub to start production collection"
