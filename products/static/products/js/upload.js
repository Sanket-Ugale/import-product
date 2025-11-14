// File upload handling with drag & drop and SSE progress tracking
let uploadJobId = null;
let eventSource = null;

// DOM elements
const dropZone = document.getElementById('dropZone');
const csvFile = document.getElementById('csvFile');
const uploadForm = document.getElementById('uploadForm');
const submitBtn = document.getElementById('submitBtn');
const submitText = document.getElementById('submitText');
const progressSection = document.getElementById('progressSection');
const dropZoneContent = document.getElementById('dropZoneContent');
const fileInfo = document.getElementById('fileInfo');

// Drag & Drop Event Handlers
dropZone.addEventListener('click', () => csvFile.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-indigo-500', 'bg-indigo-50');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        csvFile.files = files;
        handleFileSelect();
    }
});

csvFile.addEventListener('change', handleFileSelect);

function handleFileSelect() {
    const file = csvFile.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.name.endsWith('.csv')) {
        showToast('Please select a CSV file', 'error');
        clearFile();
        return;
    }
    
    // Validate file size (100MB max)
    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
        showToast('File size must be less than 100MB', 'error');
        clearFile();
        return;
    }
    
    // Show file info
    dropZoneContent.classList.add('hidden');
    fileInfo.classList.remove('hidden');
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
}

function clearFile() {
    csvFile.value = '';
    dropZoneContent.classList.remove('hidden');
    fileInfo.classList.add('hidden');
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Form submission
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const file = csvFile.files[0];
    if (!file) {
        showToast('Please select a CSV file', 'error');
        return;
    }
    
    // Disable submit button
    submitBtn.disabled = true;
    submitText.textContent = 'Uploading...';
    
    // Create FormData
    const formData = new FormData();
    formData.append('csv_file', file);
    formData.append('skip_duplicates', document.getElementById('skipDuplicates').checked);
    formData.append('deactivate_missing', document.getElementById('deactivateMissing').checked);
    
    try {
        // Upload file
        const response = await fetch('/products/upload/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok && data.job_id) {
            uploadJobId = data.job_id;
            showToast('Upload started! Tracking progress...', 'success');
            
            // Hide form, show progress
            uploadForm.classList.add('hidden');
            progressSection.classList.remove('hidden');
            
            // Start listening to SSE for progress updates
            startProgressTracking(uploadJobId);
        } else {
            showToast(data.error || 'Upload failed', 'error');
            submitBtn.disabled = false;
            submitText.textContent = 'Upload CSV';
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('An error occurred during upload', 'error');
        submitBtn.disabled = false;
        submitText.textContent = 'Upload CSV';
    }
});

// SSE Progress Tracking
function startProgressTracking(jobId) {
    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource(`/products/upload/${jobId}/progress/`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);
    };
    
    eventSource.addEventListener('complete', (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);
        handleComplete(data);
    });
    
    eventSource.addEventListener('error_event', (event) => {
        const data = JSON.parse(event.data);
        handleError(data);
    });
    
    eventSource.onerror = (error) => {
        console.error('SSE Error:', error);
        eventSource.close();
        
        // Fallback to polling
        startPolling(jobId);
    };
}

function updateProgress(data) {
    // Update progress bar
    const progress = data.progress_percentage || 0;
    document.getElementById('progressBar').style.width = progress + '%';
    document.getElementById('progressText').textContent = Math.round(progress) + '%';
    
    // Update stats
    document.getElementById('totalRows').textContent = (data.total_rows || 0).toLocaleString();
    document.getElementById('processedRows').textContent = (data.processed_rows || 0).toLocaleString();
    document.getElementById('createdCount').textContent = (data.created_count || 0).toLocaleString();
    document.getElementById('updatedCount').textContent = (data.updated_count || 0).toLocaleString();
    document.getElementById('skippedCount').textContent = (data.skipped_count || 0).toLocaleString();
    document.getElementById('errorCount').textContent = (data.error_count || 0).toLocaleString();
    
    // Update status message
    document.getElementById('statusMessage').textContent = data.status || 'Processing...';
    
    // Show errors if any
    if (data.errors && data.errors.length > 0) {
        const errorList = document.getElementById('errorList');
        const errorsUl = document.getElementById('errors');
        errorList.classList.remove('hidden');
        errorsUl.innerHTML = data.errors.slice(0, 10).map(err => 
            `<li><i class="fas fa-exclamation-circle mr-1"></i>${err}</li>`
        ).join('');
        
        if (data.errors.length > 10) {
            errorsUl.innerHTML += `<li class="text-gray-600">... and ${data.errors.length - 10} more errors</li>`;
        }
    }
}

function handleComplete(data) {
    if (eventSource) {
        eventSource.close();
    }
    
    // Remove pulse animation
    document.getElementById('progressBar').classList.remove('pulse-animation');
    
    // Show completion message
    const created = data.created_count || 0;
    const updated = data.updated_count || 0;
    const errors = data.error_count || 0;
    
    let message = `Import completed! Created: ${created}, Updated: ${updated}`;
    let type = 'success';
    
    if (errors > 0) {
        message += `, Errors: ${errors}`;
        type = 'warning';
    }
    
    showToast(message, type);
    
    // Redirect after 3 seconds
    setTimeout(() => {
        window.location.href = '/products/';
    }, 3000);
}

function handleError(data) {
    if (eventSource) {
        eventSource.close();
    }
    
    showToast(data.error || 'Import failed', 'error');
    
    // Re-enable form after 2 seconds
    setTimeout(() => {
        uploadForm.classList.remove('hidden');
        progressSection.classList.add('hidden');
        submitBtn.disabled = false;
        submitText.textContent = 'Upload CSV';
    }, 2000);
}

// Fallback polling mechanism (if SSE fails)
let pollingInterval = null;

function startPolling(jobId) {
    console.log('Falling back to polling...');
    
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/products/upload/${jobId}/status/`);
            const data = await response.json();
            
            updateProgress(data);
            
            if (data.status === 'completed') {
                clearInterval(pollingInterval);
                handleComplete(data);
            } else if (data.status === 'failed') {
                clearInterval(pollingInterval);
                handleError(data);
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000); // Poll every 2 seconds
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (eventSource) {
        eventSource.close();
    }
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
});
