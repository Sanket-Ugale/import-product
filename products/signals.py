"""
Django signals for automatic cache invalidation.
"""
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from .models import Product, UploadJob
from .services.cache_service import ProductCacheService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def invalidate_cache_on_product_save(sender, instance, created, **kwargs):
    """
    Invalidate relevant caches when a product is created or updated.
    
    Args:
        sender: Model class
        instance: Product instance
        created: Whether this is a new product
        **kwargs: Additional keyword arguments
    """
    logger.info(f"Product {'created' if created else 'updated'}: {instance.sku} (ID: {instance.id})")
    
    # Invalidate product detail cache
    ProductCacheService.invalidate_product_detail(instance.id)
    
    # Invalidate list and stats caches
    ProductCacheService.invalidate_product_list()
    ProductCacheService.invalidate_product_stats()
    
    logger.debug(f"Cache invalidated for product {instance.sku}")


@receiver(post_delete, sender=Product)
def invalidate_cache_on_product_delete(sender, instance, **kwargs):
    """
    Invalidate relevant caches when a product is deleted.
    
    Args:
        sender: Model class
        instance: Product instance
        **kwargs: Additional keyword arguments
    """
    logger.info(f"Product deleted: {instance.sku} (ID: {instance.id})")
    
    # Invalidate product detail cache
    ProductCacheService.invalidate_product_detail(instance.id)
    
    # Invalidate list and stats caches
    ProductCacheService.invalidate_product_list()
    ProductCacheService.invalidate_product_stats()
    
    logger.debug(f"Cache invalidated after deleting product {instance.sku}")


@receiver(post_save, sender=UploadJob)
def invalidate_cache_on_upload_completion(sender, instance, created, **kwargs):
    """
    Invalidate all product caches when an upload job completes.
    
    Args:
        sender: Model class
        instance: UploadJob instance
        created: Whether this is a new job
        **kwargs: Additional keyword arguments
    """
    # Only invalidate when job status changes to completed
    if not created and instance.status == 'completed':
        logger.info(f"Upload job {instance.id} completed, invalidating all product caches")
        ProductCacheService.invalidate_all_product_caches()
