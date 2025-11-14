#!/bin/bash

# Build script for Product Importer
# This script builds and sets up the development environment

set -e  # Exit on error

echo "🚀 Building Product Importer..."

# Build Docker images
echo "📦 Building Docker images..."
docker-compose build

# Start services
echo "🔄 Starting services..."
docker-compose up -d db redis

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
sleep 10

# Run migrations
echo "🗄️  Running migrations..."
docker-compose run --rm web python manage.py makemigrations
docker-compose run --rm web python manage.py migrate

# Create static directories
echo "📁 Creating static directories..."
docker-compose run --rm web mkdir -p staticfiles media/uploads

# Collect static files
echo "📦 Collecting static files..."
docker-compose run --rm web python manage.py collectstatic --noinput || true

# Start all services
echo "🚀 Starting all services..."
docker-compose up -d

# Show status
echo "✅ Setup complete!"
echo ""
echo "Services running:"
docker-compose ps

echo ""
echo "📝 Next steps:"
echo "1. Create a superuser: docker-compose exec web python manage.py createsuperuser"
echo "2. Access the application: http://localhost:8000"
echo "3. Access admin panel: http://localhost:8000/admin"
echo "4. View Celery tasks: http://localhost:5555"
echo ""
echo "View logs: docker-compose logs -f"
