"""
CSV Importer Service
Handles CSV file processing with chunked reading and bulk operations
"""

import csv
import logging
from typing import Dict, List, Tuple
from django.db import transaction
from products.models import Product, UploadJob
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CSVImporter:
    """
    Service class for importing products from CSV files
    Handles CSV format: name,sku,description
    """
    
    CHUNK_SIZE = 1000  # Process 1000 rows at a time
    REQUIRED_COLUMNS = ['name', 'sku']  # Updated to match CSV format
    OPTIONAL_COLUMNS = ['description']
    
    def __init__(self, upload_job_id: int, options: Dict = None):
        """
        Initialize importer with upload job
        
        Args:
            upload_job_id: ID of the UploadJob instance
            options: Optional dictionary with import options
        """
        self.upload_job = UploadJob.objects.get(id=upload_job_id)
        self.file_path = self.upload_job.file_path.path
        self.options = options or {}
        self.skip_duplicates = self.options.get('skip_duplicates', True)
        self.deactivate_missing = self.options.get('deactivate_missing', False)
        self.stats = {
            'total': 0,
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
    
    def validate_headers(self, headers: List[str]) -> Tuple[bool, str]:
        """
        Validate CSV headers
        
        Args:
            headers: List of column headers
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        headers_lower = [h.lower().strip() for h in headers]
        
        # Check required columns
        for required in self.REQUIRED_COLUMNS:
            if required not in headers_lower:
                return False, f"Missing required column: {required}"
        
        return True, ""
    
    def normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize and clean row data
        Handles CSV format: name,sku,description
        
        Args:
            row: Dictionary of row data
            
        Returns:
            Normalized dictionary
        """
        # Convert keys to lowercase and strip whitespace
        normalized = {}
        for k, v in row.items():
            if v is not None:
                # Clean multi-line values and excessive whitespace
                cleaned_value = ' '.join(str(v).split())
                normalized[k.lower().strip()] = cleaned_value.strip()
            else:
                normalized[k.lower().strip()] = ''
        
        # Validate required fields - must have actual values, not empty strings
        if 'sku' not in normalized or not normalized.get('sku', '').strip():
            raise ValueError("SKU is required and cannot be empty")
        
        if 'name' not in normalized or not normalized.get('name', '').strip():
            raise ValueError("Name is required and cannot be empty")
        
        # Ensure SKU is not just whitespace
        normalized['sku'] = normalized['sku'].strip()
        if not normalized['sku']:
            raise ValueError("SKU cannot be empty or contain only whitespace")
        
        # Set defaults for optional fields
        if 'description' not in normalized or not normalized['description']:
            normalized['description'] = ''
        
        # Truncate if necessary (database limits)
        normalized['sku'] = normalized['sku'][:255]
        normalized['name'] = normalized['name'][:500].strip()
        # description is TextField, no truncation needed
        
        return normalized
    
    def process_chunk(self, rows: List[Dict[str, str]]) -> None:
        """
        Process a chunk of rows with bulk operations
        
        Args:
            rows: List of row dictionaries
        """
        if not rows:
            return
        
        # Normalize all rows
        normalized_rows = []
        for idx, row in enumerate(rows):
            try:
                normalized = self.normalize_row(row)
                normalized_rows.append(normalized)
            except Exception as e:
                self.stats['errors'] += 1
                self.stats['skipped'] += 1
                self.upload_job.add_error(
                    self.stats['processed'] + idx + 1,
                    str(e)
                )
                logger.warning(f"Row {idx + 1} error: {e}")
        
        if not normalized_rows:
            return
        
        # Get all SKUs (lowercase) from this chunk - filter out empty SKUs
        skus_lower = []
        valid_rows = []
        for row in normalized_rows:
            sku = row.get('sku', '').strip()
            if sku:  # Only include rows with non-empty SKUs
                skus_lower.append(sku.lower())
                valid_rows.append(row)
            else:
                # This should not happen due to normalize_row validation, but safety check
                self.stats['errors'] += 1
                self.stats['skipped'] += 1
                logger.warning("Skipped row with empty SKU")
        
        if not valid_rows:
            logger.warning("No valid rows in chunk after filtering empty SKUs")
            return
        
        # Find existing products
        existing_products = Product.objects.filter(
            sku_lower__in=skus_lower
        ).in_bulk(field_name='sku_lower')
        
        products_to_create = []
        products_to_update = []
        
        for row in valid_rows:
            sku_lower = row['sku'].lower()
            
            if sku_lower in existing_products:
                # Update existing product
                product = existing_products[sku_lower]
                product.sku = row['sku']  # Keep original case
                product.sku_lower = row['sku'].lower().strip()  # Update sku_lower too
                product.name = row['name']
                product.description = row.get('description', '')
                products_to_update.append(product)
            else:
                # Create new product
                product = Product(
                    sku=row['sku'],
                    name=row['name'],
                    description=row.get('description', ''),
                    is_active=True
                )
                # IMPORTANT: bulk_create doesn't call save(), so set sku_lower manually
                product.sku_lower = row['sku'].lower().strip()
                products_to_create.append(product)
        
        # Bulk operations
        created_count = 0
        updated_count = 0
        
        try:
            with transaction.atomic():
                if products_to_create:
                    # For accurate counting, we need to check what actually gets created
                    # Get count before
                    before_count = Product.objects.count()
                    
                    Product.objects.bulk_create(
                        products_to_create,
                        ignore_conflicts=self.skip_duplicates
                    )
                    
                    # Get count after to see how many were actually created
                    after_count = Product.objects.count()
                    created_count = after_count - before_count
                    
                    # Track skipped duplicates
                    skipped = len(products_to_create) - created_count
                    if skipped > 0:
                        self.stats['skipped'] += skipped
                        logger.info(f"Skipped {skipped} duplicate SKUs in this chunk")
                
                if products_to_update:
                    Product.objects.bulk_update(
                        products_to_update,
                        ['sku', 'name', 'description', 'sku_lower'],
                        batch_size=500
                    )
                    updated_count = len(products_to_update)
            
            # Update stats with actual counts
            self.stats['created'] += created_count
            self.stats['updated'] += updated_count
            
        except Exception as e:
            logger.error(f"Bulk operation error: {e}")
            # Try to save products individually to identify problematic rows
            if products_to_create:
                for product in products_to_create:
                    try:
                        product.save()
                        self.stats['created'] += 1
                    except Exception as individual_error:
                        self.stats['errors'] += 1
                        self.stats['skipped'] += 1
                        logger.warning(f"Failed to create product {product.sku}: {individual_error}")
                        self.upload_job.add_error(
                            self.stats['processed'],
                            f"SKU {product.sku}: {str(individual_error)}"
                        )
    
    def update_progress(self):
        """Update job progress in database and cache"""
        self.upload_job.processed_rows = self.stats['processed']
        self.upload_job.success_count = self.stats['created'] + self.stats['updated']
        self.upload_job.error_count = self.stats['errors']
        self.upload_job.created_count = self.stats['created']
        self.upload_job.updated_count = self.stats['updated']
        self.upload_job.skipped_count = self.stats['skipped']
        self.upload_job.save(update_fields=[
            'processed_rows', 'success_count', 'error_count',
            'created_count', 'updated_count', 'skipped_count'
        ])
        
        # Update cache for real-time progress
        cache.set(
            f'upload_job_{self.upload_job.id}_progress',
            {
                'processed': self.stats['processed'],
                'total': self.stats['total'],
                'percentage': self.upload_job.progress_percentage,
                'status': self.upload_job.status,
                'created': self.stats['created'],
                'updated': self.stats['updated'],
                'errors': self.stats['errors'],
            },
            timeout=3600  # 1 hour
        )
    
    def import_csv(self) -> Dict[str, int]:
        """
        Main import method
        Handles large CSV files (800K+ rows) with proper memory management
        
        Returns:
            Dictionary with import statistics
        """
        try:
            self.upload_job.mark_as_processing()
            
            # First pass: count total rows (for progress tracking)
            logger.info("Counting total rows in CSV...")
            with open(self.file_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Validate headers
                if reader.fieldnames:
                    is_valid, error_msg = self.validate_headers(reader.fieldnames)
                    if not is_valid:
                        raise ValueError(error_msg)
                
                # Count rows efficiently
                row_count = sum(1 for _ in reader)
                self.stats['total'] = row_count
                self.upload_job.total_rows = row_count
                self.upload_job.save(update_fields=['total_rows'])
                logger.info(f"Total rows to process: {row_count}")
            
            # Second pass: process in chunks (memory efficient)
            logger.info("Starting CSV processing...")
            with open(self.file_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                chunk = []
                for idx, row in enumerate(reader, start=1):
                    chunk.append(row)
                    self.stats['processed'] += 1
                    
                    # Process chunk when full
                    if len(chunk) >= self.CHUNK_SIZE:
                        self.process_chunk(chunk)
                        chunk = []
                        self.update_progress()
                        
                        # Log progress every 10,000 rows
                        if idx % 10000 == 0:
                            logger.info(
                                f"Progress: {self.stats['processed']:,}/{self.stats['total']:,} rows "
                                f"({self.upload_job.progress_percentage}%) - "
                                f"Created: {self.stats['created']:,}, Updated: {self.stats['updated']:,}, "
                                f"Errors: {self.stats['errors']:,}"
                            )
                
                # Process remaining rows
                if chunk:
                    self.process_chunk(chunk)
                    self.update_progress()
            
            self.upload_job.mark_as_completed()
            logger.info(
                f"Import completed successfully! "
                f"Total: {self.stats['processed']:,} rows, "
                f"Created: {self.stats['created']:,}, "
                f"Updated: {self.stats['updated']:,}, "
                f"Errors: {self.stats['errors']:,}"
            )
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            self.upload_job.mark_as_failed(str(e))
            raise

