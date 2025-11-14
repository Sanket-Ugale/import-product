from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from .models import Webhook, WebhookLog
from .tasks import test_webhook


def webhook_list(request):
    """Display list of webhooks."""
    webhooks = Webhook.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(webhooks, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'webhooks': page_obj,
    }
    
    return render(request, 'webhooks/list.html', context)


def webhook_create(request):
    """Create a new webhook."""
    if request.method == 'POST':
        try:
            webhook = Webhook.objects.create(
                url=request.POST.get('url'),
                event_type=request.POST.get('event_type'),
                is_active=request.POST.get('is_active') == 'on',
                description=request.POST.get('description', '')
            )
            messages.success(request, f'Webhook for "{webhook.event_type}" created successfully!')
            return redirect('webhooks:list')
        except Exception as e:
            messages.error(request, f'Error creating webhook: {str(e)}')
    
    return render(request, 'webhooks/form.html', {'action': 'Create'})


def webhook_update(request, pk):
    """Update an existing webhook."""
    webhook = get_object_or_404(Webhook, pk=pk)
    
    if request.method == 'POST':
        try:
            webhook.url = request.POST.get('url')
            webhook.event_type = request.POST.get('event_type')
            webhook.is_active = request.POST.get('is_active') == 'on'
            webhook.description = request.POST.get('description', '')
            webhook.save()
            
            messages.success(request, f'Webhook for "{webhook.event_type}" updated successfully!')
            return redirect('webhooks:list')
        except Exception as e:
            messages.error(request, f'Error updating webhook: {str(e)}')
    
    context = {
        'webhook': webhook,
        'action': 'Update'
    }
    
    return render(request, 'webhooks/form.html', context)


@require_POST
def webhook_delete(request, pk):
    """Delete a webhook (AJAX endpoint)."""
    try:
        webhook = get_object_or_404(Webhook, pk=pk)
        event_type = webhook.event_type
        webhook.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Webhook for "{event_type}" deleted successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_POST
def webhook_test(request, pk):
    """Test a webhook (AJAX endpoint)."""
    try:
        webhook = get_object_or_404(Webhook, pk=pk)
        
        # Trigger test
        task = test_webhook.delay(webhook.id)
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': 'Test webhook triggered'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def webhook_logs(request, pk):
    """View webhook delivery logs."""
    webhook = get_object_or_404(Webhook, pk=pk)
    logs = WebhookLog.objects.filter(webhook=webhook).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'webhook': webhook,
        'logs': page_obj,
    }
    
    return render(request, 'webhooks/logs.html', context)


@require_POST
def webhook_toggle(request, pk):
    """Toggle webhook active status (AJAX endpoint)."""
    try:
        webhook = get_object_or_404(Webhook, pk=pk)
        webhook.is_active = not webhook.is_active
        webhook.save()
        
        return JsonResponse({
            'success': True,
            'is_active': webhook.is_active
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

