"""
Webhook admin configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Webhook, WebhookLog


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    """Admin interface for Webhook model"""
    
    list_display = [
        'id', 'event_type', 'url_display', 'is_active_badge',
        'success_rate_display', 'total_triggers', 'last_triggered_at'
    ]
    list_filter = ['event_type', 'is_active', 'created_at']
    search_fields = ['url', 'event_type', 'description']
    readonly_fields = [
        'secret', 'total_triggers', 'successful_triggers', 'failed_triggers',
        'last_triggered_at', 'last_success_at', 'last_failure_at',
        'created_at', 'updated_at', 'success_rate'
    ]
    list_per_page = 25
    
    fieldsets = (
        ('Webhook Configuration', {
            'fields': ('url', 'event_type', 'description', 'is_active')
        }),
        ('Security', {
            'fields': ('secret',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_triggers', 'successful_triggers', 'failed_triggers',
                'success_rate'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'last_triggered_at', 'last_success_at', 'last_failure_at',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def url_display(self, obj):
        """Display truncated URL"""
        return obj.url[:50] + '...' if len(obj.url) > 50 else obj.url
    url_display.short_description = 'URL'
    
    def is_active_badge(self, obj):
        """Display active status as badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; '
            'border-radius: 3px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def success_rate_display(self, obj):
        """Display success rate as progress bar"""
        rate = obj.success_rate
        color = '#28a745' if rate >= 80 else '#ffc107' if rate >= 50 else '#dc3545'
        return format_html(
            '<div style="width: 80px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; color: white; '
            'text-align: center; padding: 2px; border-radius: 3px; font-size: 11px;">{}%</div>'
            '</div>',
            rate, color, rate
        )
    success_rate_display.short_description = 'Success Rate'


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    """Admin interface for WebhookLog model"""
    
    list_display = [
        'id', 'webhook_event', 'status_badge', 'status_code',
        'response_time_display', 'retry_count', 'created_at'
    ]
    list_filter = ['event_type', 'is_successful', 'created_at']
    search_fields = ['webhook__url', 'event_type', 'error']
    readonly_fields = [
        'webhook', 'event_type', 'payload', 'status_code',
        'response_body', 'response_time', 'error', 'is_successful',
        'retry_count', 'created_at'
    ]
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        """Disable adding logs manually"""
        return False
    
    def webhook_event(self, obj):
        """Display webhook and event type"""
        return f"{obj.webhook.url[:30]}... - {obj.event_type}"
    webhook_event.short_description = 'Webhook'
    
    def status_badge(self, obj):
        """Display status as badge"""
        if obj.is_successful:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px;">Success</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
            'border-radius: 3px;">Failed</span>'
        )
    status_badge.short_description = 'Result'
    
    def response_time_display(self, obj):
        """Display response time"""
        if obj.response_time:
            return f"{obj.response_time:.2f}s"
        return "-"
    response_time_display.short_description = 'Response Time'
