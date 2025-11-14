from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Product CRUD
    path('', views.product_list, name='list'),
    path('<int:pk>/', views.product_detail, name='detail'),
    path('create/', views.product_create, name='create'),
    path('<int:pk>/update/', views.product_update, name='update'),
    path('<int:pk>/delete/', views.product_delete, name='delete'),
    
    # CSV Upload
    path('upload/', views.upload_csv, name='upload'),
    path('upload/<int:job_id>/progress/', views.upload_progress, name='upload_progress'),
    path('upload/<int:job_id>/status/', views.upload_status, name='upload_status'),
    path('upload/jobs/', views.upload_jobs, name='upload_jobs'),
    
    # Bulk Operations
    path('bulk-activate/', views.bulk_activate, name='bulk_activate'),
    path('bulk-deactivate/', views.bulk_deactivate, name='bulk_deactivate'),
    path('bulk-delete/', views.bulk_delete_view, name='bulk_delete'),
    
    # Export
    path('export/', views.export_products, name='export'),
]

