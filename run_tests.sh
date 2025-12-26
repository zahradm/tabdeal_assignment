#!/bin/bash

# Quick test runner script
# Runs all tests and displays results

set -e

echo "=================================================="
echo "Running B2B Charge Sales System Tests"
echo "=================================================="
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "[1/2] Running Django unit tests..."
echo "------------------------------------------------"
python manage.py test sales -v 2
echo ""

echo "[2/2] Running concurrent load tests..."
echo "------------------------------------------------"
python test_concurrent.py
echo ""

echo "=================================================="
echo "All Tests Completed!"
echo "=================================================="
