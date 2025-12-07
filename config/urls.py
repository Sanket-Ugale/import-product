"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from products.auth_views import login_page, logout, get_token_page
from products.auth_views import CustomTokenObtainPairView, LogoutView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication
    path('login/', login_page, name='login'),
    path('logout/', logout, name='logout'),
    path('tokens/', get_token_page, name='tokens'),
    
    # JWT API endpoints
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/logout/', LogoutView.as_view(), name='api_logout'),
    
    # Products app
    path('products/', include('products.urls')),
    
    # Webhooks app
    path('webhooks/', include('webhooks.urls')),
    
    # Redirect root to products
    path('', RedirectView.as_view(url='/products/', permanent=False)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "Product Importer Administration"
admin.site.site_title = "Product Importer Admin"
admin.site.index_title = "Welcome to Product Importer Admin"

