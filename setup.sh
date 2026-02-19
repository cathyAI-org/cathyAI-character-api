#!/bin/bash
# Development environment setup script for cathyAI Character API

echo "Setting up cathyAI Character API development environment..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Create .env from template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.template .env
    echo "✓ .env file created (please configure it)"
else
    echo "✓ .env file exists"
fi

# Check if character files exist
if [ ! -f "characters/catherine.json" ]; then
    echo "⚠️  Warning: Character files not found in characters/"
fi

if [ ! -f "public/avatars/catherine_pfp.jpg" ]; then
    echo "⚠️  Warning: Avatar files not found in public/avatars/"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run the API locally:"
echo "  uvicorn app:app --host 0.0.0.0 --port 8090"
echo ""
echo "To run with Docker:"
echo "  docker-compose up --build"
echo ""
echo "To run tests:"
echo "  pytest tests/"
