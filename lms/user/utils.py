from django.contrib.sessions.models import Session
from django.utils.timezone import now
from user.models import EmployeeProfile,TraineeProfile,CustomUser
from django.db.models import Q
from django.utils import timezone

def get_active_users(department: str):
    # 1) Who has a live session?
    active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
    user_ids = {
        s.get_decoded().get('_auth_user_id')
        for s in active_sessions
        if '_auth_user_id' in s.get_decoded()
    }
    if not user_ids:
        return CustomUser.objects.none()

    # 2) Users who are active AND belong to this department
    #    either via TraineeProfile OR EmployeeProfile
    qs = (
        CustomUser.objects
        .filter(id__in=user_ids)
        .filter(
            Q(trainee_profile__department=department) |
            Q(employee_profile__department=department)
        )
        .distinct()
    )

    # (Optional) Prefetch related profiles for efficiency
    qs = qs.prefetch_related('trainee_profile', 'employee_profile')

    return qs