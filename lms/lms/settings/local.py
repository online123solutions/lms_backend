from .base import *
from decouple import config
from corsheaders.defaults import default_headers


ALLOWED_HOSTS = ['localhost','127.0.0.1']

DEBUG=True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Local frontend during development:
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  
    "http://127.0.0.1:3000",
    "https://lmsfrontend-ki924.ondigitalocean.app"
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",  
    "http://127.0.0.1:3000",
    "https://lmsfrontend-ki924.ondigitalocean.app"
]

CORS_ALLOW_CREDENTIALS = True

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Celery settings
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'shahnawaz.1504ali@gmail.com'
EMAIL_HOST_PASSWORD = 'lfuu cfmq zmtd txgf'  # Ensure this is the correct App Password
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'shahnawaz.1504ali@gmail.com' 
EMAIL_TIMEOUT = 10  # Seconds

# Redis for channels backend
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}