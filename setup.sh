#!/bin/bash

# Setup script for B2B Charge Sales System
# This script automates the initial setup process

set -e  # Exit on error

echo "=================================================="
echo "B2B Charge Sales System - Setup Script"
echo "=================================================="
echo ""

# Check Python version
echo "[1/8] Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "Error: Python 3 is not installed"
    exit 1
fi
echo "✓ Python 3 is installed"
echo ""

# Create virtual environment
echo "[2/8] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "[3/8] Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "[4/8] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
echo "[5/8] Setting up environment variables..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Created .env file from .env.example"
    echo "  Please edit .env with your database credentials"
else
    echo "✓ .env file already exists"
fi
echo ""

# Check PostgreSQL connection
echo "[6/8] Checking database connection..."
echo "Please ensure PostgreSQL is running and configured in .env"
read -p "Press Enter to continue when database is ready..."
echo ""

# Run migrations
echo "[7/8] Running database migrations..."
python manage.py makemigrations
python manage.py migrate
echo "✓ Migrations completed"
echo ""

# Create superuser
echo "[8/8] Creating superuser..."
echo "You can skip this if you already have a superuser"
read -p "Do you want to create a superuser? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
    echo "✓ Superuser created"
else
    echo "✓ Skipped superuser creation"
fi
echo ""

echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your database credentials (if not done)"
echo "2. Run: python manage.py runserver"
echo "3. Access admin at: http://localhost:8000/admin/"
echo "4. Run tests: python manage.py test sales"
echo "5. Run concurrent tests: python test_concurrent.py"
echo ""
echo "Documentation:"
echo "- README.md - Complete usage guide"
echo "- ARCHITECTURE.md - System architecture details"
echo ""
