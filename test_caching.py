#!/usr/bin/env python
"""
Test script to demonstrate caching functionality.
Run this to see the difference between cached and non-cached queries.
"""
import os
import django
import time
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db import connection, reset_queries
from products.models import Product
from products.services.cache_service import ProductCacheService

def count_queries():
    """Return the number of database queries executed."""
    return len(connection.queries)

def test_with_caching():
    """Test performance with caching enabled."""
    print("\n" + "="*60)
    print("TESTING WITH CACHING ENABLED")
    print("="*60)
    
    # Clear cache first
    from django.core.cache import cache
    cache.clear()
    reset_queries()
    
    # Define a stats function
    def get_stats():
        return {
            'total_count': Product.objects.count(),
            'active_count': Product.objects.filter(is_active=True).count(),
            'inactive_count': Product.objects.filter(is_active=False).count(),
        }
    
    # First call - should hit database
    print("\n1️⃣ First call (Cache MISS - should query database):")
    reset_queries()
    start = time.time()
    stats1 = ProductCacheService.get_cached_product_stats(get_stats)
    elapsed1 = time.time() - start
    queries1 = count_queries()
    print(f"   Stats: {stats1}")
    print(f"   Time: {elapsed1*1000:.2f}ms")
    print(f"   Database queries: {queries1}")
    
    # Second call - should use cache
    print("\n2️⃣ Second call (Cache HIT - should use cache):")
    reset_queries()
    start = time.time()
    stats2 = ProductCacheService.get_cached_product_stats(get_stats)
    elapsed2 = time.time() - start
    queries2 = count_queries()
    print(f"   Stats: {stats2}")
    print(f"   Time: {elapsed2*1000:.2f}ms")
    print(f"   Database queries: {queries2}")
    
    # Show improvement
    if queries1 > 0 and queries2 == 0:
        print(f"\n✅ Cache is working! Reduced queries from {queries1} to {queries2}")
        print(f"   Speed improvement: {(elapsed1/elapsed2):.1f}x faster")
    else:
        print(f"\n⚠️  Unexpected result - check if caching is enabled")

def test_without_caching():
    """Test performance with caching disabled."""
    print("\n" + "="*60)
    print("TESTING WITH CACHING DISABLED")
    print("="*60)
    print("(To test this, set ENABLE_CACHING=False in .env)")
    
    # Check if caching is enabled
    if ProductCacheService.is_caching_enabled():
        print("\n⚠️  Caching is currently ENABLED")
        print("   To test without caching:")
        print("   1. Edit .env and set ENABLE_CACHING=False")
        print("   2. Restart the server: docker-compose restart web")
        print("   3. Run this script again")
    else:
        print("\n✅ Caching is DISABLED - all queries will hit database")
        
        def get_stats():
            return {
                'total_count': Product.objects.count(),
                'active_count': Product.objects.filter(is_active=True).count(),
                'inactive_count': Product.objects.filter(is_active=False).count(),
            }
        
        # Both calls should hit database
        print("\n1️⃣ First call:")
        reset_queries()
        stats1 = ProductCacheService.get_cached_product_stats(get_stats)
        queries1 = count_queries()
        print(f"   Stats: {stats1}")
        print(f"   Database queries: {queries1}")
        
        print("\n2️⃣ Second call:")
        reset_queries()
        stats2 = ProductCacheService.get_cached_product_stats(get_stats)
        queries2 = count_queries()
        print(f"   Stats: {stats2}")
        print(f"   Database queries: {queries2}")
        
        if queries1 > 0 and queries2 > 0:
            print(f"\n✅ No caching - both calls hit database as expected")
        else:
            print(f"\n⚠️  Unexpected result")

if __name__ == '__main__':
    print("\n🔍 Redis Caching Test Script")
    print(f"📊 Total products in database: {Product.objects.count()}")
    print(f"🔧 Caching enabled: {ProductCacheService.is_caching_enabled()}")
    
    test_with_caching()
    test_without_caching()
    
    print("\n" + "="*60)
    print("Test completed!")
    print("="*60 + "\n")
