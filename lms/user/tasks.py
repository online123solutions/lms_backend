from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from fcm_django.models import FCMDevice 
from django.apps import apps
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
import logging
logger = logging.getLogger(__name__)

@shared_task
def send_welcome_email(email):
    subject = "Welcome to the LMS"
    message = "Hi! Welcome to our Learning Management System. We're excited to have you onboard."
    from_email = settings.DEFAULT_FROM_EMAIL

    send_mail(subject, message, from_email, [email])


@shared_task
def send_notification_email(email, subject, message):
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
    return f"Notification sent to {email}"


@shared_task
def send_push_notification(user_ids, title, message):
    """
    Sends push notifications to the specified users.
    """
    # Get CustomUser dynamically to avoid import issues
    CustomUser = apps.get_model("user", "CustomUser")

    # Ensure user_ids are valid
    users = CustomUser.objects.filter(id__in=user_ids)
    if not users.exists():
        return "⚠️ No valid users found."

    # Fetch devices linked to users
    devices = FCMDevice.objects.filter(user_id__in=user_ids)
    
    if devices.exists():
        # Send notification
        devices.send_message(title=title, body=message)

        return f"Push notifications sent to {devices.count()} users"
    
    return "No devices found for push notifications."

@shared_task
def send_email_to_trainer(subject, message, email):
    """
    Asynchronous task to send email to the trainer.
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,  # Your default 'from' email
        [email],  # List of recipient emails
        fail_silently=False,
    )
    return f"Email sent to {email}"

@shared_task
def send_password_reset_email(email):
    from .models import CustomUser
    if not email:
        return "User with email None does not exist"

    try:
        user = CustomUser.objects.get(email=email)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"http://127.0.0.1:8000/account/password-reset-confirm/{uid}/{token}/"
        logger.info(f"Generated reset link: {reset_link}")  # Log the generated link
        subject = "Password Reset Request"
        message = f"Use this link to reset your password: {reset_link}"

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False
        )
        logger.info(f"Email sent successfully to {email}")
        return f"✅ Password reset email sent to {email}"
    except CustomUser.DoesNotExist:
        return f"User with email {email} does not exist"
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {str(e)}")
        return f"Failed to send email to {email}: {str(e)}"