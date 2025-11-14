"""
Celery tasks for product operations
"""

import logging
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_csv_import(self, upload_job_id, options=None):
    """
    Process CSV import asynchronously
    
    Args:
        upload_job_id: ID of the UploadJob
        options: Optional dictionary with import options (skip_duplicates, deactivate_missing)
        
    Returns:
        Dictionary with import statistics
    """
    from products.models import UploadJob
    from products.services.csv_importer import CSVImporter
    
    if options is None:
        options = {}
    
    try:
        logger.info(f"Starting CSV import for job {upload_job_id} with options: {options}")
        
        # Update task ID in upload job
        upload_job = UploadJob.objects.get(id=upload_job_id)
        upload_job.task_id = self.request.id
        upload_job.save(update_fields=['task_id'])
        
        # Create importer and process
        importer = CSVImporter(upload_job_id, options=options)
        stats = importer.import_csv()
        
        logger.info(f"CSV import completed for job {upload_job_id}: {stats}")
        
        # Trigger webhook
        trigger_webhooks.delay('upload.completed', {
            'upload_job_id': upload_job_id,
            'file_name': upload_job.file_name,
            'stats': stats
        })
        
        return stats
        
    except Exception as e:
        logger.error(f"CSV import failed for job {upload_job_id}: {e}")
        
        # Trigger failure webhook
        try:
            trigger_webhooks.delay('upload.failed', {
                'upload_job_id': upload_job_id,
                'error': str(e)
            })
        except:
            pass
        
        raise


@shared_task
def bulk_delete_products(product_ids):
    """
    Delete products by IDs asynchronously
    
    Args:
        product_ids: List of product IDs to delete
        
    Returns:
        Number of products deleted
    """
    from products.models import Product, AuditLog
    
    try:
        logger.info(f"Starting bulk delete of {len(product_ids)} products")
        
        # Get products to delete
        products = Product.objects.filter(id__in=product_ids)
        count = products.count()
        
        # Get SKUs for audit log
        skus = list(products.values_list('sku', flat=True))
        
        # Create audit log
        AuditLog.objects.create(
            product_sku='BULK_DELETE',
            action='bulk_delete',
            changes={
                'deleted_count': count,
                'product_ids': product_ids,
                'skus': skus[:100]  # Limit to first 100 for storage
            },
            user='system'
        )
        
        # Delete products
        products.delete()
        
        logger.info(f"Bulk delete completed: {count} products deleted")
        
        # Trigger webhook
        trigger_webhooks.delay('product.bulk_deleted', {
            'deleted_count': count
        })
        
        return count
        
    except Exception as e:
        logger.error(f"Bulk delete failed: {e}")
        raise


@shared_task
def cleanup_old_upload_jobs(days=30):
    """
    Clean up old upload jobs (keep records but delete files)
    
    Args:
        days: Number of days to keep
        
    Returns:
        Number of jobs cleaned
    """
    from products.models import UploadJob
    import os
    
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_jobs = UploadJob.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed']
        )
        
        count = 0
        for job in old_jobs:
            # Delete the file if it exists
            if job.file_path and os.path.exists(job.file_path.path):
                os.remove(job.file_path.path)
                logger.info(f"Deleted file for job {job.id}")
                count += 1
        
        logger.info(f"Cleanup completed: {count} files deleted")
        return count
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise


@shared_task
def trigger_webhooks(event_type, payload):
    """
    Trigger webhooks for an event
    
    Args:
        event_type: Type of event
        payload: Event payload data
    """
    from webhooks.models import Webhook
    from webhooks.tasks import send_webhook
    
    try:
        # Find active webhooks for this event type
        webhooks = Webhook.objects.filter(
            event_type=event_type,
            is_active=True
        )
        
        logger.info(f"Triggering {webhooks.count()} webhooks for event: {event_type}")
        
        # Trigger each webhook asynchronously
        for webhook in webhooks:
            send_webhook.delay(webhook.id, payload)
        
    except Exception as e:
        logger.error(f"Failed to trigger webhooks: {e}")


@shared_task
def update_product_stats():
    """
    Update product statistics in cache
    For dashboard and analytics
    """
    from products.models import Product, UploadJob
    from django.db.models import Count, Q
    
    try:
        stats = {
            'total_products': Product.objects.count(),
            'active_products': Product.objects.filter(is_active=True).count(),
            'inactive_products': Product.objects.filter(is_active=False).count(),
            'total_uploads': UploadJob.objects.count(),
            'pending_uploads': UploadJob.objects.filter(status='pending').count(),
            'processing_uploads': UploadJob.objects.filter(status='processing').count(),
            'completed_uploads': UploadJob.objects.filter(status='completed').count(),
            'failed_uploads': UploadJob.objects.filter(status='failed').count(),
        }
        
        cache.set('product_stats', stats, timeout=300)  # 5 minutes
        logger.info("Product stats updated")
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to update stats: {e}")
        raise


@shared_task
def export_products_csv(filters=None):
    """
    Export products to CSV file
    
    Args:
        filters: Optional filters to apply
        
    Returns:
        Path to generated CSV file
    """
    from products.models import Product
    import csv
    import os
    from django.conf import settings
    
    try:
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'products_export_{timestamp}.csv'
        filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Get products
        products = Product.objects.all()
        if filters:
            # Apply filters if provided
            pass
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['SKU', 'Name', 'Description', 'Status', 'Created At'])
            
            for product in products.iterator(chunk_size=1000):
                writer.writerow([
                    product.sku,
                    product.name,
                    product.description,
                    'Active' if product.is_active else 'Inactive',
                    product.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ])
        
        logger.info(f"Export completed: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise

