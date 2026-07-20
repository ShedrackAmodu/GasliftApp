# Celery import is optional - only required if using async task processing
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except (ImportError, ModuleNotFoundError):
    # Celery not installed - async task processing disabled
    pass