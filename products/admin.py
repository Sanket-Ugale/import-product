"""
Product admin configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Product, UploadJob, AuditLog


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin interface for Product model"""
    
    list_display = ['sku', 'name', 'is_active_badge', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['sku', 'sku_lower', 'name', 'description']
    readonly_fields = ['sku_lower', 'created_at', 'updated_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Product Information', {
            'fields': ('sku', 'sku_lower', 'name', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_badge(self, obj):
        """Display active status as badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
            'border-radius: 3px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'


@admin.register(UploadJob)
class UploadJobAdmin(admin.ModelAdmin):
    """Admin interface for UploadJob model"""
    
    list_display = [
        'id', 'file_name', 'status_badge', 'progress_bar',
        'total_rows', 'success_count', 'error_count', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['file_name', 'task_id']
    readonly_fields = [
        'file_name', 'file_path', 'task_id', 'total_rows',
        'processed_rows', 'success_count', 'error_count',
        'created_count', 'updated_count', 'skipped_count',
        'started_at', 'completed_at', 'created_at', 'updated_at',
        'progress_percentage', 'duration'
    ]
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('File Information', {
            'fields': ('file_name', 'file_path', 'task_id')
        }),
        ('Status', {
            'fields': ('status', 'progress_percentage')
        }),
        ('Statistics', {
            'fields': (
                'total_rows', 'processed_rows', 'success_count', 'error_count',
                'created_count', 'updated_count', 'skipped_count'
            )
        }),
        ('Error Details', {
            'fields': ('error_details',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at', 'duration', 'created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#6c757d',
            'processing': '#007bff',
            'completed': '#28a745',
            'failed': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def progress_bar(self, obj):
        """Display progress as a progress bar"""
        percentage = obj.progress_percentage
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; background-color: #007bff; color: white; '
            'text-align: center; padding: 2px; border-radius: 3px; font-size: 11px;">{}%</div>'
            '</div>',
            percentage, percentage
        )
    progress_bar.short_description = 'Progress'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog model"""
    
    list_display = ['id', 'product_sku', 'action_badge', 'user', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['product_sku', 'user', 'ip_address']
    readonly_fields = ['product_sku', 'action', 'changes', 'user', 'ip_address', 'timestamp']
    list_per_page = 50
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        """Disable adding audit logs manually"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deleting audit logs"""
        return False
    
    def action_badge(self, obj):
        """Display action as badge"""
        colors = {
            'create': '#28a745',
            'update': '#007bff',
            'delete': '#dc3545',
            'bulk_delete': '#dc3545',
            'import': '#17a2b8',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            colors.get(obj.action, '#6c757d'),
            obj.get_action_display()
        )
    action_badge.short_description = 'Action'
