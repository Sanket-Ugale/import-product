from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.cache import cache
import json
import time
import csv

from .models import Product, UploadJob, AuditLog
from .tasks import process_csv_import, bulk_delete_products, export_products_csv, trigger_webhooks
from .services.cache_service import ProductCacheService
from webhooks.models import Webhook


@login_required(login_url='login')
@ensure_csrf_cookie
def product_list(request):
    """Display paginated list of products with search and filters (with caching)."""
    # Get query parameters
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort_by', 'updated_at')
    order = request.GET.get('order', 'desc')
    page_number = request.GET.get('page', 1)
    
    # Validate sort_by to prevent SQL injection
    allowed_sort_fields = ['updated_at', 'created_at', 'name', 'sku']
    if sort_by not in allowed_sort_fields:
        sort_by = 'updated_at'
    
    # Build queryset
    products = Product.objects.all()
    
    # Search
    if search_query:
        products = products.filter(
            Q(sku__icontains=search_query) | 
            Q(name__icontains=search_query)
        )
    
    # Status filter
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    
    # Apply sorting
    if order == 'asc':
        products = products.order_by(sort_by)
    else:
        products = products.order_by(f'-{sort_by}')
    
    # Pagination
    paginator = Paginator(products, 50)  # 50 products per page
    page_obj = paginator.get_page(page_number)
    
    # Get cached stats
    def get_stats():
        return {
            'total_count': Product.objects.count(),
            'active_count': Product.objects.filter(is_active=True).count(),
            'inactive_count': Product.objects.filter(is_active=False).count(),
            'last_updated': Product.objects.order_by('-updated_at').first(),
        }
    
    stats = ProductCacheService.get_cached_product_stats(get_stats)
    
    context = {
        'products': page_obj,
        'total_count': stats['total_count'],
        'active_count': stats['active_count'],
        'inactive_count': stats['inactive_count'],
        'last_updated': stats['last_updated'].updated_at if stats['last_updated'] else None,
    }
    
    return render(request, 'products/list.html', context)


@login_required(login_url='login')
@ensure_csrf_cookie
def product_detail(request, pk):
    """Display product details (with caching)."""
    def get_product_data():
        product = get_object_or_404(Product, pk=pk)
        return {
            'id': product.id,
            'sku': product.sku,
            'name': product.name,
            'description': product.description,
            'is_active': product.is_active,
            'created_at': product.created_at,
            'updated_at': product.updated_at,
        }
    
    # Get cached product data
    product_data = ProductCacheService.get_cached_product_detail(pk, get_product_data)
    
    # Get audit logs (not cached as they're frequently updated)
    audit_logs = AuditLog.objects.filter(product_sku=product_data['sku']).order_by('-timestamp')[:10]
    
    context = {
        'product': type('Product', (), product_data)(),  # Convert dict to object for template
        'audit_logs': audit_logs,
    }
    
    return render(request, 'products/detail.html', context)


@login_required(login_url='login')
def product_create(request):
    """Create a new product."""
    if request.method == 'POST':
        try:
            product = Product.objects.create(
                sku=request.POST.get('sku'),
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                is_active=request.POST.get('is_active') == 'on'
            )
            
            # Trigger webhook
            trigger_webhooks.delay('product.created', {
                'product_id': product.id,
                'sku': product.sku,
                'name': product.name,
                'is_active': product.is_active,
                'created_at': product.created_at.isoformat()
            })
            
            messages.success(request, f'Product "{product.sku}" created successfully!')
            return redirect('products:detail', pk=product.id)
        except Exception as e:
            messages.error(request, f'Error creating product: {str(e)}')
    
    return render(request, 'products/form.html', {'action': 'Create'})


@login_required(login_url='login')
def product_update(request, pk):
    """Update an existing product."""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        try:
            # Store old values for webhook payload
            old_name = product.name
            old_is_active = product.is_active
            
            product.name = request.POST.get('name')
            product.description = request.POST.get('description', '')
            product.is_active = request.POST.get('is_active') == 'on'
            product.save()
            
            # Trigger webhook
            trigger_webhooks.delay('product.updated', {
                'product_id': product.id,
                'sku': product.sku,
                'name': product.name,
                'is_active': product.is_active,
                'updated_at': product.updated_at.isoformat(),
                'changes': {
                    'name': {'old': old_name, 'new': product.name},
                    'is_active': {'old': old_is_active, 'new': product.is_active}
                }
            })
            
            messages.success(request, f'Product "{product.sku}" updated successfully!')
            return redirect('products:detail', pk=product.id)
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
    
    context = {
        'product': product,
        'action': 'Update'
    }
    
    return render(request, 'products/form.html', context)


@login_required(login_url='login')
@require_POST
def product_delete(request, pk):
    """Delete a product (AJAX endpoint)."""
    try:
        product = get_object_or_404(Product, pk=pk)
        sku = product.sku
        product_data = {
            'product_id': product.id,
            'sku': product.sku,
            'name': product.name,
            'deleted_at': timezone.now().isoformat()
        }
        
        product.delete()
        
        # Trigger webhook
        trigger_webhooks.delay('product.deleted', product_data)
        
        return JsonResponse({
            'success': True,
            'message': f'Product "{sku}" deleted successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required(login_url='login')
@ensure_csrf_cookie
def upload_csv(request):
    """Handle CSV file upload and initiate processing."""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'error': 'File must be a CSV'}, status=400)
        
        try:
            # Create upload job
            upload_job = UploadJob.objects.create(
                file_name=csv_file.name,
                file_path=csv_file,
                total_rows=0,  # Will be updated during processing
                status='pending'
            )
            
            # Trigger webhook for upload started
            trigger_webhooks.delay('upload.started', {
                'job_id': upload_job.id,
                'file_name': csv_file.name,
                'started_at': upload_job.created_at.isoformat()
            })
            
            # Start async processing
            options = {
                'skip_duplicates': request.POST.get('skip_duplicates') == 'true',
                'deactivate_missing': request.POST.get('deactivate_missing') == 'true',
            }
            
            task = process_csv_import.delay(upload_job.id, options)
            upload_job.task_id = task.id
            upload_job.save()
            
            return JsonResponse({
                'success': True,
                'job_id': upload_job.id,
                'task_id': task.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return render(request, 'products/upload.html')


@login_required(login_url='login')
def upload_progress(request, job_id):
    """SSE endpoint for real-time upload progress."""
    def event_stream():
        upload_job = get_object_or_404(UploadJob, id=job_id)
        
        while True:
            # Refresh from database
            upload_job.refresh_from_db()
            
            # Prepare progress data
            data = {
                'status': upload_job.status,
                'progress_percentage': upload_job.progress_percentage,
                'total_rows': upload_job.total_rows,
                'processed_rows': upload_job.processed_rows,
                'created_count': upload_job.created_count,
                'updated_count': upload_job.updated_count,
                'skipped_count': upload_job.skipped_count,
                'error_count': upload_job.error_count,
                'errors': upload_job.errors[:10] if upload_job.errors else [],
            }
            
            # Send event
            if upload_job.status == 'completed':
                yield f"event: complete\ndata: {json.dumps(data)}\n\n"
                break
            elif upload_job.status == 'failed':
                yield f"event: error_event\ndata: {json.dumps(data)}\n\n"
                break
            else:
                yield f"data: {json.dumps(data)}\n\n"
            
            time.sleep(1)  # Update every second
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    
    return response


@login_required(login_url='login')
def upload_status(request, job_id):
    """Get upload job status (polling fallback)."""
    upload_job = get_object_or_404(UploadJob, id=job_id)
    
    data = {
        'status': upload_job.status,
        'progress_percentage': upload_job.progress_percentage,
        'total_rows': upload_job.total_rows,
        'processed_rows': upload_job.processed_rows,
        'created_count': upload_job.created_count,
        'updated_count': upload_job.updated_count,
        'skipped_count': upload_job.skipped_count,
        'error_count': upload_job.error_count,
        'errors': upload_job.errors[:10] if upload_job.errors else [],
    }
    
    return JsonResponse(data)


@login_required(login_url='login')
def upload_jobs(request):
    """Display upload job history."""
    jobs = UploadJob.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'jobs': page_obj,
    }
    
    return render(request, 'products/upload_jobs.html', context)


@login_required(login_url='login')
@require_POST
def bulk_activate(request):
    """Bulk activate products (AJAX endpoint)."""
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        
        # Get SKUs before update for webhook
        skus = list(Product.objects.filter(id__in=product_ids).values_list('sku', flat=True))
        
        count = Product.objects.filter(id__in=product_ids).update(is_active=True)
        
        # Invalidate cache for affected products
        ProductCacheService.invalidate_products(product_ids)
        
        # Trigger webhook
        if count > 0:
            trigger_webhooks.delay('product.updated', {
                'action': 'bulk_activate',
                'count': count,
                'product_ids': product_ids,
                'skus': skus[:100],  # Limit for payload size
                'updated_at': timezone.now().isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='login')
@require_POST
def bulk_deactivate(request):
    """Bulk deactivate products (AJAX endpoint)."""
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        
        # Get SKUs before update for webhook
        skus = list(Product.objects.filter(id__in=product_ids).values_list('sku', flat=True))
        
        count = Product.objects.filter(id__in=product_ids).update(is_active=False)
        
        # Invalidate cache for affected products
        ProductCacheService.invalidate_products(product_ids)
        
        # Trigger webhook
        if count > 0:
            trigger_webhooks.delay('product.updated', {
                'action': 'bulk_deactivate',
                'count': count,
                'product_ids': product_ids,
                'skus': skus[:100],  # Limit for payload size
                'updated_at': timezone.now().isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='login')
@require_POST
def bulk_delete_view(request):
    """Bulk delete products (AJAX endpoint) - async task."""
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        
        # Start async deletion
        task = bulk_delete_products.delay(product_ids)
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'count': len(product_ids)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='login')
def export_products(request):
    """Export products to CSV."""
    # Start async export
    task = export_products_csv.delay()
    
    messages.info(request, 'Export started! You will be notified when ready.')
    return redirect('products:list')
