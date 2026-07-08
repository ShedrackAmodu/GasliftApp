#!/bin/bash
# Gas Lift Application Setup Script for macOS/Linux

echo ""
echo "========================================"
echo "Gas Lift Opportunity Automation System"
echo "========================================"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "Error creating virtual environment"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error installing dependencies"
    exit 1
fi

# Run migrations
echo "Running database migrations..."
python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Error running migrations"
    exit 1
fi

# Create demo user
echo "Creating demo user..."
python create_demo_user.py

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To start the development server, run:"
echo "  source venv/bin/activate"
echo "  python manage.py runserver"
echo ""
echo "Then open your browser to: http://localhost:8000"
echo ""
echo "Demo username: demo"
echo "Demo password: demo123"
echo ""
echo "Admin interface: http://localhost:8000/admin"
echo ""
