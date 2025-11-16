"""
Cache service for managing product-related caching.
"""
from django.core.cache import cache
from django.db.models import QuerySet
from django.conf import settings
import hashlib
import json
from typing import Any, Optional, Callable


class ProductCacheService:
    """Service for managing product caching with automatic invalidation."""
    
    # Cache key prefixes
    PRODUCT_LIST_PREFIX = "product_list"
    PRODUCT_DETAIL_PREFIX = "product_detail"
    PRODUCT_STATS_PREFIX = "product_stats"
    PRODUCT_COUNT_PREFIX = "product_count"
    
    # Cache timeouts (in seconds)
    LIST_TIMEOUT = 300  # 5 minutes
    DETAIL_TIMEOUT = 600  # 10 minutes
    STATS_TIMEOUT = 180  # 3 minutes
    
    @staticmethod
    def is_caching_enabled() -> bool:
        """Check if caching is enabled in settings."""
        return getattr(settings, 'ENABLE_CACHING', True)
    
    @staticmethod
    def _generate_cache_key(prefix: str, **kwargs) -> str:
        """
        Generate a unique cache key based on prefix and parameters.
        
        Args:
            prefix: Cache key prefix
            **kwargs: Parameters to include in the key
            
        Returns:
            Unique cache key string
        """
        # Sort kwargs to ensure consistent key generation
        sorted_params = sorted(kwargs.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"{prefix}:{param_hash}"
    
    @classmethod
    def get_product_list_key(cls, search: str = '', status: str = '', 
                            sort_by: str = 'updated_at', order: str = 'desc', 
                            page: int = 1) -> str:
        """Generate cache key for product list."""
        return cls._generate_cache_key(
            cls.PRODUCT_LIST_PREFIX,
            search=search,
            status=status,
            sort_by=sort_by,
            order=order,
            page=page
        )
    
    @classmethod
    def get_product_detail_key(cls, product_id: int) -> str:
        """Generate cache key for product detail."""
        return f"{cls.PRODUCT_DETAIL_PREFIX}:{product_id}"
    
    @classmethod
    def get_product_stats_key(cls) -> str:
        """Generate cache key for product statistics."""
        return cls.PRODUCT_STATS_PREFIX
    
    @classmethod
    def get_or_set(cls, key: str, callback: Callable, timeout: int = None) -> Any:
        """
        Get value from cache or execute callback and cache the result.
        
        Args:
            key: Cache key
            callback: Function to execute if cache miss
            timeout: Cache timeout in seconds
            
        Returns:
            Cached or newly computed value
        """
        # If caching is disabled, always execute callback
        if not cls.is_caching_enabled():
            return callback()
        
        value = cache.get(key)
        if value is None:
            value = callback()
            cache.set(key, value, timeout)
        return value
    
    @classmethod
    def invalidate_product_list(cls):
        """Invalidate all product list caches."""
        # Skip if caching is disabled
        if not cls.is_caching_enabled():
            return
        
        try:
            # Delete all keys matching the product list pattern
            # Use django-redis specific method
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            # Note: django-redis automatically adds KEY_PREFIX, so we search with it
            pattern = f"product_importer:{cls.PRODUCT_LIST_PREFIX}:*"
            keys = redis_conn.keys(pattern)
            if keys:
                redis_conn.delete(*keys)
        except Exception as e:
            # Fallback: just clear entire cache if pattern delete fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to delete pattern, clearing entire cache: {e}")
            cache.clear()
    
    @classmethod
    def invalidate_product_detail(cls, product_id: int):
        """Invalidate cache for a specific product."""
        # Skip if caching is disabled
        if not cls.is_caching_enabled():
            return
        
        key = cls.get_product_detail_key(product_id)
        cache.delete(key)
    
    @classmethod
    def invalidate_product_stats(cls):
        """Invalidate product statistics cache."""
        # Skip if caching is disabled
        if not cls.is_caching_enabled():
            return
        
        cache.delete(cls.PRODUCT_STATS_PREFIX)
    
    @classmethod
    def invalidate_all_product_caches(cls):
        """Invalidate all product-related caches."""
        # Skip if caching is disabled
        if not cls.is_caching_enabled():
            return
        
        try:
            # Delete all product-related cache keys
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            
            # Delete list caches
            list_keys = redis_conn.keys(f"product_importer:{cls.PRODUCT_LIST_PREFIX}:*")
            if list_keys:
                redis_conn.delete(*list_keys)
            
            # Delete detail caches
            detail_keys = redis_conn.keys(f"product_importer:{cls.PRODUCT_DETAIL_PREFIX}:*")
            if detail_keys:
                redis_conn.delete(*detail_keys)
            
            # Delete stats cache
            cls.invalidate_product_stats()
        except Exception as e:
            # Fallback: just clear entire cache if pattern delete fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to delete patterns, clearing entire cache: {e}")
            cache.clear()
    
    @classmethod
    def invalidate_products(cls, product_ids: list = None):
        """
        Invalidate caches for specific products or all products.
        
        Args:
            product_ids: List of product IDs to invalidate, or None for all
        """
        # Skip if caching is disabled
        if not cls.is_caching_enabled():
            return
        
        # Always invalidate list and stats
        cls.invalidate_product_list()
        cls.invalidate_product_stats()
        
        if product_ids:
            # Invalidate specific products
            for product_id in product_ids:
                cls.invalidate_product_detail(product_id)
        else:
            # Invalidate all product details
            try:
                from django_redis import get_redis_connection
                redis_conn = get_redis_connection("default")
                detail_keys = redis_conn.keys(f"product_importer:{cls.PRODUCT_DETAIL_PREFIX}:*")
                if detail_keys:
                    redis_conn.delete(*detail_keys)
            except Exception:
                # Fallback: clear all if pattern delete fails
                cache.clear()
    
    @classmethod
    def get_cached_product_list(cls, queryset: QuerySet, search: str = '', 
                                status: str = '', sort_by: str = 'updated_at',
                                order: str = 'desc', page: int = 1):
        """
        Get cached product list or cache the queryset result.
        
        Args:
            queryset: Product queryset to cache
            search: Search query
            status: Status filter
            sort_by: Sort field
            order: Sort order
            page: Page number
            
        Returns:
            List of products
        """
        key = cls.get_product_list_key(search, status, sort_by, order, page)
        
        def fetch_products():
            # Convert queryset to list to cache it
            return list(queryset.values(
                'id', 'sku', 'name', 'description', 'is_active', 
                'created_at', 'updated_at'
            ))
        
        return cls.get_or_set(key, fetch_products, cls.LIST_TIMEOUT)
    
    @classmethod
    def get_cached_product_stats(cls, stats_callback: Callable) -> dict:
        """
        Get cached product statistics.
        
        Args:
            stats_callback: Function that returns stats dict
            
        Returns:
            Dictionary with product statistics
        """
        key = cls.get_product_stats_key()
        return cls.get_or_set(key, stats_callback, cls.STATS_TIMEOUT)
    
    @classmethod
    def get_cached_product_detail(cls, product_id: int, detail_callback: Callable) -> dict:
        """
        Get cached product detail.
        
        Args:
            product_id: Product ID
            detail_callback: Function that returns product dict
            
        Returns:
            Product detail dictionary
        """
        key = cls.get_product_detail_key(product_id)
        return cls.get_or_set(key, detail_callback, cls.DETAIL_TIMEOUT)
