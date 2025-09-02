import django
from django.conf import settings

# ✅ Setup Django before Celery is loaded
django.setup()

from .celery import app as celery_app  # Import Celery AFTER Django setup

__all__ = ('celery_app',)
