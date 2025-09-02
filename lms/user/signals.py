from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import CustomUser, TraineeProfile, EmployeeProfile, TrainerProfile, AdminProfile,UserLoginActivity,AssessmentReport
from django.utils.timezone import now
from django.core.cache import cache
import logging
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from quiz.models import Result

error_log = logging.getLogger('error_log')
# Helper function to get client IP
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'trainee':
            TraineeProfile.objects.create(user=instance)
        elif instance.role == 'employee':
            EmployeeProfile.objects.create(user=instance)
        elif instance.role == 'trainer':
            TrainerProfile.objects.create(user=instance)
        elif instance.role == 'admin':
            AdminProfile.objects.create(user=instance)

@receiver(user_logged_in)
def log_user_logged_in_success(sender, user, request, **kwargs):

    ct = cache.get('count', 0, version=user.username)
    newcount = ct + 1
    cache.set('count', newcount, 60 * 60 * 24 * 365, version=user.username)

    request.session['last_login'] = str(timezone.now())

    try:
        user_agent_info = request.META.get('HTTP_USER_AGENT', '<unknown>')[:255]
        login_time = timezone.now()

        login_count = cache.get('count', version=user.username)

        user_login_activity_log = UserLoginActivity(
            login_IP=get_client_ip(request),
            login_datetime=login_time,
            login_num=login_count,
            login_username=user.username,
            user_agent_info=user_agent_info,
            status=UserLoginActivity.SUCCESS
        )
        user_login_activity_log.save()

    except Exception as e:
        error_log.error(f"log_user_logged_in request: {request}, error: {e}")


@receiver(post_save, sender=Result)
def update_homework_report(sender, instance, **kwargs):

    try:
        trainee = TraineeProfile.objects.filter(user=instance.user).first()
        if not trainee:
            print(f"No Student found for user: {instance.user}")
            return
        
        report, created = AssessmentReport.objects.get_or_create(quiz=instance.quiz)
        report.update_report()
        report.save()
        print(f"Homework report updated successfully for -{instance.quiz}")

    except ObjectDoesNotExist as e:
        print(f"Object Does Not Exist: {e}")

    except Exception as e:
        print(f"Error updating homework report: {e}")