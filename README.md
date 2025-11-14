# Product Importer - Django Application

A scalable web application for importing and managing 500K+ products from CSV files.

## 🚀 Features

### Core Features
- ✅ **CSV Import** - Upload large CSV files (500K+ records) with real-time progress tracking
- ✅ **Product Management** - Full CRUD operations with filtering, search, and pagination
- ✅ **Bulk Operations** - Delete all products with confirmation
- ✅ **Webhook Management** - Configure webhooks for product events
- ✅ **Progress Tracking** - Real-time SSE-based upload progress
- ✅ **Case-Insensitive SKU** - Unique SKU handling with case insensitivity

### Extra Features
- 📊 **Audit Logs** - Complete audit trail of all product changes
- 📈 **Dashboard** - Overview of products, uploads, and system stats
- 📥 **Export CSV** - Export products to CSV format
- 🔍 **Advanced Search** - Full-text search across products
- 📊 **Webhook Logs** - Detailed logging of webhook deliveries
- 🌸 **Flower** - Celery task monitoring dashboard
- 🎨 **Modern UI** - Clean interface with TailwindCSS

## 🛠 Tech Stack

- **Backend**: Django 5.0, Python 3.11
- **Task Queue**: Celery with Redis broker
- **Database**: PostgreSQL 15
- **Cache**: Redis
- **Frontend**: Django Templates + TailwindCSS + Vanilla JS
- **Containerization**: Docker & Docker Compose
- **Web Server**: Gunicorn + Nginx

## 📋 Prerequisites

- Docker & Docker Compose
- Git

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/sanket-ugale/import-product.git
cd import-product
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` if needed (default values work for development).

### 3. Build and run with Docker

```bash
# Build containers
docker-compose build

# Start services
docker-compose up -d

# Check if services are running
docker-compose ps
```

### 4. Run migrations

```bash
docker-compose exec web python manage.py migrate
```

### 5. Create superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

### 6. Access the application

- **Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **Flower (Celery Monitor)**: http://localhost:5555


## 🔧 Development

### Running management commands

```bash
# Make migrations
docker-compose exec web python manage.py makemigrations

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Django shell
docker-compose exec web python manage.py shell
```

### Viewing logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f celery
docker-compose logs -f db
docker-compose logs -f redis
```

### Stopping services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: This deletes all data)
docker-compose down -v
```

## 📤 CSV Import Format

Your CSV file should have the following format:

```csv
name,sku,description
Product Name 1,PROD-001,Product description here
Product Name 2,PROD-002,Another description
```

**Column Specifications:**
- `name` - Product name (required, max 500 characters)
- `sku` - Stock Keeping Unit (required, max 255 characters, case-insensitive unique)
- `description` - Product description (optional, unlimited length, can be multi-line)

**Notes:**
- SKU is case-insensitive and must be unique
- Duplicates will be updated (overwritten) based on SKU
- Products not in CSV won't be deleted
- Maximum file size: 100MB
- Handles multi-line descriptions and special characters
- Current test file: 861,686 rows, 86MB

**Sample Files:**
- `products.csv` - Full dataset (861K rows)
- `products_sample.csv` - Test sample (100 rows)

For detailed CSV format documentation, see [CSV_FORMAT.md](CSV_FORMAT.md).

## 🎯 API Endpoints

### Products
- `GET /products/` - List products
- `POST /products/create/` - Create product
- `GET /products/<id>/` - Product detail
- `POST /products/<id>/update/` - Update product
- `POST /products/<id>/delete/` - Delete product
- `POST /products/bulk-delete/` - Delete all products

### Upload
- `GET /products/upload/` - Upload page
- `POST /products/upload/` - Submit CSV
- `GET /products/upload/progress/<job_id>/` - SSE progress
- `GET /products/upload/jobs/` - Upload history

### Webhooks
- `GET /webhooks/` - List webhooks
- `POST /webhooks/create/` - Create webhook
- `POST /webhooks/<id>/update/` - Update webhook
- `POST /webhooks/<id>/delete/` - Delete webhook
- `POST /webhooks/<id>/test/` - Test webhook

## 🔒 Security Features

- CSRF protection enabled
- XSS protection
- SQL injection protection via ORM
- Webhook HMAC signature verification
- File upload validation
- Rate limiting (production)

## 📊 Monitoring

### Celery Flower

Access Flower dashboard at http://localhost:5555 to monitor:
- Active tasks
- Task history
- Worker status
- Task statistics

### Admin Panel

Access admin at http://localhost:8000/admin to view:
- Products
- Upload jobs
- Webhooks
- Audit logs
- Webhook logs
