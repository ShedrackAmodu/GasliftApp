"""
URL configuration for gaslift_project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/upload/', include('apps.data_upload.urls')),
    path('api/analysis/', include('apps.analysis.urls')),
    path('api/results/', include('apps.results.urls')),
    path('', views.dashboard, name='dashboard'),
    path('contact/', TemplateView.as_view(template_name='base/contact.html'), name='contact'),
    path('user-manual/', TemplateView.as_view(template_name='base/user_manual.html'), name='user_manual'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
