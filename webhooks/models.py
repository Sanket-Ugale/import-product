"""
Webhook application models
"""

from django.db import models
from django.core.validators import URLValidator
from django.utils import timezone
import secrets


class Webhook(models.Model):
    """
    Webhook configuration for event notifications
    """
    EVENT_CHOICES = [
        ('product.created', 'Product Created'),
        ('product.updated', 'Product Updated'),
        ('product.deleted', 'Product Deleted'),
        ('product.bulk_deleted', 'Products Bulk Deleted'),
        ('upload.started', 'Upload Started'),
        ('upload.completed', 'Upload Completed'),
        ('upload.failed', 'Upload Failed'),
    ]

    url = models.URLField(
        max_length=500,
        validators=[URLValidator()],
        help_text="The endpoint URL to send webhook POST requests to"
    )
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_CHOICES,
        db_index=True,
        help_text="The type of event that triggers this webhook"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this webhook is active"
    )
    secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret key for HMAC signature verification"
    )
    description = models.TextField(blank=True, default='')
    
    # Statistics
    total_triggers = models.IntegerField(default=0)
    successful_triggers = models.IntegerField(default=0)
    failed_triggers = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'webhooks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'is_active'], name='idx_webhook_event_active'),
            models.Index(fields=['-created_at'], name='idx_webhook_created'),
        ]
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'

    def __str__(self):
        return f"{self.event_type} -> {self.url[:50]}"

    def save(self, *args, **kwargs):
        """Generate secret if not provided"""
        if not self.secret:
            self.secret = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def record_trigger(self, success=True):
        """Record a webhook trigger attempt"""
        self.total_triggers += 1
        self.last_triggered_at = timezone.now()
        
        if success:
            self.successful_triggers += 1
            self.last_success_at = timezone.now()
        else:
            self.failed_triggers += 1
            self.last_failure_at = timezone.now()
        
        self.save(update_fields=[
            'total_triggers', 'successful_triggers', 'failed_triggers',
            'last_triggered_at', 'last_success_at', 'last_failure_at'
        ])

    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_triggers == 0:
            return 0
        return int((self.successful_triggers / self.total_triggers) * 100)


class WebhookLog(models.Model):
    """
    Log of webhook delivery attempts
    Extra feature for debugging and monitoring
    """
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    event_type = models.CharField(max_length=50, db_index=True)
    payload = models.JSONField(default=dict)
    
    # Response details
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default='')
    response_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Response time in seconds"
    )
    
    # Error details
    error = models.TextField(blank=True, default='')
    is_successful = models.BooleanField(default=False, db_index=True)
    retry_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'webhook_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='idx_webhook_log_created'),
            models.Index(fields=['is_successful'], name='idx_webhook_log_success'),
            models.Index(fields=['event_type'], name='idx_webhook_log_event'),
        ]
        verbose_name = 'Webhook Log'
        verbose_name_plural = 'Webhook Logs'

    def __str__(self):
        status = "✓" if self.is_successful else "✗"
        return f"{status} {self.webhook.event_type} - {self.status_code}"
