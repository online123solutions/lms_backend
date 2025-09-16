from .base import *
from pathlib import Path

ALLOWED_HOSTS = ['139.59.81.107']
DEBUG=False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

SWAGGER_SETTINGS = {
    'USE_HTTPS': True,
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
        }
    },
    'schemes': ['https'],
}

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
]

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
]

SECURE_CROSS_ORIGIN_OPENER_POLICY = None
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # Allow frontend to access it
CSRF_COOKIE_SAMESITE = "None"  # Required for cross-origin requests

CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'  # ✅ Add this if missing

SECURE_CROSS_ORIGIN_OPENER_POLICY = None
CSRF_COOKIE_SECURE = True

# Import tasks automatically
CELERY_IMPORTS = ("user.tasks",)

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Use your email provider's SMTP host
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'shahnawaz.1504ali@gmail.com'
EMAIL_HOST_PASSWORD = 'lfuu cfmq zmtd txgf'  # Use App Password for Gmail
DEFAULT_FROM_EMAIL = 'shahnawaz.1504ali@gmail.com'