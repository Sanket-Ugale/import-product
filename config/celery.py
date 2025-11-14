"""
Celery configuration for product_importer project.
"""

import os
from celery import Celery
from decouple import config

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('product_importer')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule (for periodic tasks)
app.conf.beat_schedule = {
    # Example: Clean up old upload jobs every day
    'cleanup-old-jobs': {
        'task': 'products.tasks.cleanup_old_upload_jobs',
        'schedule': 86400.0,  # 24 hours
    },
}


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')
