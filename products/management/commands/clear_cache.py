"""
Management command to clear all product caches
"""
from django.core.management.base import BaseCommand
from products.services.cache_service import ProductCacheService
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Clear all product-related caches'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear all cache (not just product caches)',
        )

    def handle(self, *args, **options):
        if options['all']:
            # Clear entire cache
            cache.clear()
            self.stdout.write(
                self.style.SUCCESS('Successfully cleared all cache')
            )
        else:
            # Clear only product caches
            ProductCacheService.invalidate_all_product_caches()
            self.stdout.write(
                self.style.SUCCESS('Successfully cleared product caches')
            )
