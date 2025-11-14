"""
Webhook Celery tasks
"""

import logging
import requests
import hmac
import hashlib
import time
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_webhook(self, webhook_id, payload):
    """
    Send webhook POST request with retries
    
    Args:
        webhook_id: ID of the Webhook
        payload: Data to send
        
    Returns:
        Response status code
    """
    from webhooks.models import Webhook, WebhookLog
    
    try:
        webhook = Webhook.objects.get(id=webhook_id)
        
        # Generate HMAC signature
        secret = webhook.secret.encode('utf-8')
        message = str(payload).encode('utf-8')
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Event-Type': webhook.event_type,
            'User-Agent': 'ProductImporter-Webhook/1.0'
        }
        
        # Send request with timeout
        start_time = time.time()
        response = requests.post(
            webhook.url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response_time = time.time() - start_time
        
        # Log the attempt
        is_successful = 200 <= response.status_code < 300
        
        WebhookLog.objects.create(
            webhook=webhook,
            event_type=webhook.event_type,
            payload=payload,
            status_code=response.status_code,
            response_body=response.text[:1000],  # Limit to 1000 chars
            response_time=response_time,
            is_successful=is_successful,
            retry_count=self.request.retries
        )
        
        # Update webhook statistics
        webhook.record_trigger(success=is_successful)
        
        if not is_successful:
            logger.warning(
                f"Webhook {webhook_id} returned {response.status_code}"
            )
            # Retry on failure
            raise Exception(f"Webhook failed with status {response.status_code}")
        
        logger.info(f"Webhook {webhook_id} delivered successfully in {response_time:.2f}s")
        return response.status_code
        
    except requests.RequestException as e:
        logger.error(f"Webhook {webhook_id} request failed: {e}")
        
        # Log the error
        try:
            webhook = Webhook.objects.get(id=webhook_id)
            WebhookLog.objects.create(
                webhook=webhook,
                event_type=webhook.event_type,
                payload=payload,
                error=str(e),
                is_successful=False,
                retry_count=self.request.retries
            )
            webhook.record_trigger(success=False)
        except Exception:
            pass
        
        # Retry
        raise self.retry(exc=e)
        
    except Exception as e:
        logger.error(f"Webhook {webhook_id} failed: {e}")
        raise


@shared_task
def test_webhook(webhook_id):
    """
    Test a webhook with sample payload
    
    Args:
        webhook_id: ID of the Webhook
        
    Returns:
        Tuple of (success, message, response_time)
    """
    from webhooks.models import Webhook
    
    try:
        webhook = Webhook.objects.get(id=webhook_id)
        
        test_payload = {
            'event': 'test',
            'message': 'This is a test webhook',
            'timestamp': timezone.now().isoformat()
        }
        
        # Generate HMAC signature
        secret = webhook.secret.encode('utf-8')
        message = str(test_payload).encode('utf-8')
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Event-Type': 'test',
            'User-Agent': 'ProductImporter-Webhook/1.0'
        }
        
        # Send request
        start_time = time.time()
        response = requests.post(
            webhook.url,
            json=test_payload,
            headers=headers,
            timeout=10
        )
        response_time = time.time() - start_time
        
        is_successful = 200 <= response.status_code < 300
        
        if is_successful:
            return True, f"Success ({response.status_code})", response_time
        else:
            return False, f"Failed ({response.status_code})", response_time
            
    except requests.RequestException as e:
        return False, f"Request failed: {str(e)}", 0
    except Exception as e:
        return False, f"Error: {str(e)}", 0


@shared_task
def cleanup_old_webhook_logs(days=30):
    """
    Clean up old webhook logs
    
    Args:
        days: Number of days to keep
        
    Returns:
        Number of logs deleted
    """
    from webhooks.models import WebhookLog
    from datetime import timedelta
    
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        
        count, _ = WebhookLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Deleted {count} old webhook logs")
        return count
        
    except Exception as e:
        logger.error(f"Failed to cleanup webhook logs: {e}")
        raise

