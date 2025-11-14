"""
Product application models
"""

from django.db import models
from django.core.validators import MinLengthValidator
from django.utils import timezone
import json


class Product(models.Model):
    """
    Product model with case-insensitive unique SKU
    """
    sku = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(1)],
        help_text="Stock Keeping Unit (SKU) - case insensitive unique identifier"
    )
    sku_lower = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Lowercase version of SKU for case-insensitive uniqueness"
    )
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sku_lower'], name='idx_sku_lower'),
            models.Index(fields=['is_active'], name='idx_is_active'),
            models.Index(fields=['-created_at'], name='idx_created_at'),
            models.Index(fields=['name'], name='idx_name'),
        ]
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def save(self, *args, **kwargs):
        """Override save to ensure sku_lower is always set"""
        self.sku_lower = self.sku.lower().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def status(self):
        """Return human-readable status"""
        return "Active" if self.is_active else "Inactive"


class UploadJob(models.Model):
    """
    Track CSV upload jobs and their progress
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    file_name = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='uploads/%Y/%m/%d/', max_length=500)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    created_count = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    
    error_details = models.JSONField(null=True, blank=True, default=list)
    task_id = models.CharField(max_length=255, blank=True, null=True)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'upload_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='idx_upload_created'),
            models.Index(fields=['status'], name='idx_upload_status'),
        ]
        verbose_name = 'Upload Job'
        verbose_name_plural = 'Upload Jobs'

    def __str__(self):
        return f"Upload Job {self.id} - {self.file_name} ({self.status})"

    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.total_rows == 0:
            return 0
        return int((self.processed_rows / self.total_rows) * 100)

    @property
    def duration(self):
        """Calculate duration of the job"""
        if self.started_at:
            end_time = self.completed_at or timezone.now()
            return (end_time - self.started_at).total_seconds()
        return 0

    @property
    def errors(self):
        """Return list of error messages"""
        if self.error_details:
            return [error.get('error', '') for error in self.error_details]
        return []

    def add_error(self, row_number, error_message):
        """Add an error to the error details"""
        if self.error_details is None:
            self.error_details = []
        
        self.error_details.append({
            'row': row_number,
            'error': str(error_message),
            'timestamp': timezone.now().isoformat()
        })
        self.error_count += 1
        self.save(update_fields=['error_details', 'error_count'])

    def mark_as_processing(self):
        """Mark job as processing"""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_as_completed(self):
        """Mark job as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def mark_as_failed(self, error_message=None):
        """Mark job as failed"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        if error_message:
            self.add_error(0, error_message)
        self.save(update_fields=['status', 'completed_at'])


class AuditLog(models.Model):
    """
    Audit log for tracking changes to products
    Extra feature for compliance and debugging
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('bulk_delete', 'Bulk Delete'),
        ('import', 'Import'),
    ]

    product_sku = models.CharField(max_length=255, db_index=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    changes = models.JSONField(default=dict, blank=True)
    user = models.CharField(max_length=255, default='system')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp'], name='idx_audit_timestamp'),
            models.Index(fields=['product_sku'], name='idx_audit_sku'),
            models.Index(fields=['action'], name='idx_audit_action'),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        return f"{self.action} - {self.product_sku} at {self.timestamp}"
