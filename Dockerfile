FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=lms.settings.staging

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY lms/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    psycopg2-binary \
    daphne \
    gunicorn \
    whitenoise

COPY lms/ .

RUN mkdir -p /app/staticfiles /app/media

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "lms.asgi:application"]
