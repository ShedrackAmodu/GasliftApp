"""
Celery configuration for async task processing.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaslift_config.settings')

app = Celery('gaslift_config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()