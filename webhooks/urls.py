from django.urls import path
from . import views

app_name = 'webhooks'

urlpatterns = [
    path('', views.webhook_list, name='list'),
    path('create/', views.webhook_create, name='create'),
    path('<int:pk>/update/', views.webhook_update, name='update'),
    path('<int:pk>/delete/', views.webhook_delete, name='delete'),
    path('<int:pk>/test/', views.webhook_test, name='test'),
    path('<int:pk>/logs/', views.webhook_logs, name='logs'),
    path('<int:pk>/toggle/', views.webhook_toggle, name='toggle'),
]

