from .base import *
from pathlib import Path

ALLOWED_HOSTS = ['lms.steel.study', 'steel.study', '127.0.0.1', 'localhost','app.steel.study']

DEBUG=True

# at the bottom is fine
STATIC_URL = "static/"
STATIC_ROOT = "/opt/myapi/lms_backend/lms/staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = "/opt/myapi/lms_backend/lms/media"

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
    "https://lmsfrontend-ki924.ondigitalocean.app",
    "https://steel.study",
    "https://www.steel.study",
    "https://app.steel.study",
    "https://www.app.steel.study"
]

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    "https://lmsfrontend-ki924.ondigitalocean.app",
    "https://steel.study",
    "https://www.steel.study",
    "https://app.steel.study",
    "https://www.app.steel.study",
    "https://lms.steel.study",
    "https://lms.staging.steel.study"
]

CORS_ALLOW_CREDENTIALS = True

SECURE_CROSS_ORIGIN_OPENER_POLICY = None
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # Allow frontend to access it
CSRF_COOKIE_SAMESITE = "None"  # Required for cross-origin requests

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "None"  # Required for cross-origin requests

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

# ---- static config (explicit absolute path) ----
STATIC_URL = "static/"
STATIC_ROOT = "/opt/myapi/lms_backend/lms/staticfiles"
