from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    CustomUser, TraineeProfile, EmployeeProfile, TrainerProfile,AdminProfile,Courses, CourseLesson,Macroplanner,Microplanner,Assessment, AssessmentReport,EvaluationRemark
    ,TrainingReport,UserLoginActivity,Query,QueryResponse,Subject,Lesson,Notification,NotificationReceipt
)
from django.contrib.auth import authenticate
from quiz.serializers import ResultSerializer
from django.urls import reverse
from quiz.models import Quiz,Result
from urllib.parse import urljoin
from django.conf import settings
from django.db import IntegrityError

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'email', 'role')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data['role'],
            is_active=False
        )
        return user

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.set_password(validated_data.get('password', instance.password))
        if validated_data.get('role'):
            instance.role = validated_data.get('role')
        if instance.is_active:
            instance.is_active = False
        instance.save()
        return instance

class TraineeSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()

    class Meta:
        model = TraineeProfile
        fields = ['user','name', 'employee_id', 'department', 'designation', 'trainer','profile_picture']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.filter(username=user_data['username']).first()
        if not user:
            user_serializer = CustomUserSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        else:
            user_serializer = CustomUserSerializer(instance=user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation', 'trainer','profile_picture']}
        profile, created = TraineeProfile.objects.get_or_create(user=user, defaults=profile_data)
        if not created:
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()
        return profile

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user')
        user_serializer = CustomUserSerializer(instance=instance.user, data=user_data, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation', 'trainer','profile_picture']}
        for key, value in profile_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance

class EmployeeSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()

    class Meta:
        model = EmployeeProfile
        fields = ['name','user', 'employee_id', 'department', 'designation','profile_picture']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.filter(username=user_data['username']).first()
        if not user:
            user_serializer = CustomUserSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        else:
            user_serializer = CustomUserSerializer(instance=user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation','profile_picture']}
        profile, created = EmployeeProfile.objects.get_or_create(user=user, defaults=profile_data)
        if not created:
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()
        return profile

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user')
        user_serializer = CustomUserSerializer(instance=instance.user, data=user_data, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation','profile_picture']}
        for key, value in profile_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance

class TrainerSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()

    class Meta:
        model = TrainerProfile
        fields = ['user','name', 'employee_id', 'department', 'designation', 'expertise']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.filter(username=user_data['username']).first()
        if not user:
            user_serializer = CustomUserSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        else:
            user_serializer = CustomUserSerializer(instance=user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation', 'expertise','profile_picture']}
        profile, created = TrainerProfile.objects.get_or_create(user=user, defaults=profile_data)
        if not created:
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()
        return profile

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user')
        user_serializer = CustomUserSerializer(instance=instance.user, data=user_data, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation', 'expertise','profile_picture']}
        for key, value in profile_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
class AdminSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()

    class Meta:
        model = AdminProfile
        fields = ['user','name', 'employee_id', 'department', 'designation','profile_picture']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.filter(username=user_data['username']).first()
        if not user:
            user_serializer = CustomUserSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        else:
            user_serializer = CustomUserSerializer(instance=user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation','profile_picture']}
        profile, created = AdminProfile.objects.get_or_create(user=user, defaults=profile_data)
        if not created:
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()
        return profile

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user')
        user_serializer = CustomUserSerializer(instance=instance.user, data=user_data, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        profile_data = {k: v for k, v in validated_data.items() if k in ['name','employee_id', 'department', 'designation','profile_picture']}
        for key, value in profile_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username or password")
        
        data['user'] = user
        return data
    
class UserExcelUploadSerializer(serializers.Serializer):
    excel_file = serializers.FileField()

    def validate_excel_file(self, value):
        if not value.name.endswith('.xlsx'):
            raise serializers.ValidationError("Only .xlsx files are allowed.")
        return value
    

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courses
        fields = [
            'id',
            'course_id',
            'course_name',
            'department',
            'display_on_frontend',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class CourseLessonSerializer(serializers.ModelSerializer):
    # Original extras
    course_name = serializers.CharField(source='course.course_name', read_only=True)

    # Frontend-friendly aliases
    name = serializers.CharField(source='lesson_name', read_only=True)
    courseId = serializers.IntegerField(source='course.id', read_only=True)
    courseName = serializers.CharField(source='course.course_name', read_only=True)

    # Absolute-URL fields for viewers
    lessonPlanUrl = serializers.SerializerMethodField()
    lessonPpt = serializers.SerializerMethodField()
    videoUrl = serializers.SerializerMethodField()

    # (Optional) also override originals to be absolute if you want:
    lesson_plans = serializers.SerializerMethodField()
    lesson_ppt = serializers.SerializerMethodField()
    lesson_video = serializers.SerializerMethodField()

    class Meta:
        model = CourseLesson
        fields = [
            # model fields
            'id',
            'lesson_id',
            'lesson_name',
            'course',
            'course_name',
            'lesson_video',
            'lesson_plans',
            'lesson_ppt',
            'lesson_editor',
            'display_on_frontend',
            'is_approved',
            'created_by',
            'created_at',
            'updated_at',

            # aliases for frontend
            'name',
            'courseId',
            'courseName',
            'lessonPlanUrl',
            'lessonPpt',
            'videoUrl',
        ]
        read_only_fields = [
            'id', 'course_name', 'created_by', 'created_at', 'updated_at',
            'name', 'courseId', 'courseName', 'lessonPlanUrl', 'lessonPpt', 'videoUrl'
        ]

    # -------- helpers --------
    def _abs(self, url_path: str | None) -> str | None:
        """Return absolute URL for a given storage URL path."""
        if not url_path:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url_path)
        # Fallback if serializer used without request in context
        base = getattr(settings, 'SITE_BASE_URL', None) or getattr(settings, 'FRONTEND_ORIGIN', None)
        return urljoin(base, url_path) if base else url_path

    # Aliases your React consumes
    def get_lessonPlanUrl(self, obj):
        try:
            return self._abs(obj.lesson_plans.url)
        except Exception:
            return None

    def get_lessonPpt(self, obj):
        try:
            return self._abs(obj.lesson_ppt.url)
        except Exception:
            return None

    def get_videoUrl(self, obj):
        try:
            # If it's a FileField/URLField. If you store bare URLs, return as-is.
            return self._abs(obj.lesson_video.url) if hasattr(obj.lesson_video, 'url') else (obj.lesson_video or None)
        except Exception:
            return None

    # (Optional) Make original fields absolute too so both work
    def get_lesson_plans(self, obj):
        try:
            return self._abs(obj.lesson_plans.url)
        except Exception:
            return None

    def get_lesson_ppt(self, obj):
        try:
            return self._abs(obj.lesson_ppt.url)
        except Exception:
            return None

    def get_lesson_video(self, obj):
        try:
            return self._abs(obj.lesson_video.url) if hasattr(obj.lesson_video, 'url') else (obj.lesson_video or None)
        except Exception:
            return None

class MacroplannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Macroplanner
        fields = ['id','week', 'duration', 'month', 'department', 'module','mode']


class MicroplannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Microplanner
        fields = ['id', 'month', 'week', 'days','department', 'no_of_sessions', 'name_of_topic','mode']


class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = '__all__'
        read_only_fields = ['assigned_by', 'created_at']


class AssessmentReportSerializer(serializers.ModelSerializer):
    results = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentReport
        fields = "__all__"

    def get_results(self, obj):
        """
        Return attempts with user details:
        - display_name, username, role
        - department, designation
        - score, quiz, date_attempted
        """
        qs = (
            Result.objects
            .filter(quiz=obj.quiz)
            .select_related(
                "user",
                "user__trainee_profile",
                "user__employee_profile",
            )
            .order_by("-date_attempted", "-id")
        )

        # If your AssessmentReport has an 'audience' field, respect it.
        audience = getattr(obj, "audience", None)
        if audience in {"trainee", "employee"}:
            qs = qs.filter(user__role=audience)

        out = []
        for r in qs:
            u = r.user
            role = getattr(u, "role", None)

            display_name = u.get_full_name() or u.username
            department = ""
            designation = ""

            if role == "employee" and hasattr(u, "employee_profile") and u.employee_profile:
                p = u.employee_profile
                display_name = p.name or display_name
                department = p.department or ""
                designation = p.designation or ""
            elif role == "trainee" and hasattr(u, "trainee_profile") and u.trainee_profile:
                p = u.trainee_profile
                display_name = p.name or display_name
                department = p.department or ""
                designation = p.designation or ""

            out.append({
                "id": r.id,
                "username": u.username,
                "display_name": display_name,
                "department": department,
                "designation": designation,
                "role": role,
                "score": r.score,
                "quiz": r.quiz_id,
                "date_attempted": r.date_attempted,
            })

        return out

    def to_representation(self, instance):
        instance.update_report()  # keep your live metrics refresh
        return super().to_representation(instance)


class EvaluationRemarkSerializer(serializers.ModelSerializer):
    trainee_name = serializers.CharField(source='trainee.username', read_only=True)
    trainer_name = serializers.CharField(source='trainer.username', read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)

    class Meta:
        model = EvaluationRemark
        fields = '__all__'
        read_only_fields = ['trainer', 'created_at']


class TrainingReportSerializer(serializers.ModelSerializer):
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)

    class Meta:
        model = TrainingReport
        fields = '__all__'


class UserLoginActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLoginActivity
        fields = ['login_username','login_datetime', 'login_num']

class QueryResponseSerializer(serializers.ModelSerializer):
    responder = serializers.PrimaryKeyRelatedField(read_only=True)
    responder_username = serializers.CharField(source='responder.username', read_only=True)
    responder_role = serializers.CharField(source='responder.role', read_only=True)
    responded_at = serializers.DateTimeField(read_only=True)
    sender_type = serializers.SerializerMethodField()  # 'trainee' or 'trainer'

    class Meta:
        model = QueryResponse
        fields = [
            'id',
            'response',
            'responder',
            'responder_username',
            'responder_role',
            'responded_at',
            'sender_type',          # ✅ new
        ]
        read_only_fields = ['responder', 'responder_username', 'responder_role', 'responded_at', 'sender_type']

    def get_sender_type(self, obj):
        # Adjust 'query' below if your FK name differs
        try:
            return 'trainee' if obj.responder_id == obj.query.raised_by_id else 'trainer'
        except Exception:
            # Safe fallback if anything is missing
            return 'trainer'

class QuerySerializer(serializers.ModelSerializer):
    raised_by = serializers.StringRelatedField()
    assigned_trainer = serializers.StringRelatedField()
    responses = QueryResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Query
        fields = [
            'id',
            'raised_by', 'assigned_trainer', 'notify_trainer', 'department',
            'question', 'category', 'is_resolved', 'created_at',
            'raised_by_role', 'responses'
        ]

    def create(self, validated_data):
        user = validated_data['raised_by']
        validated_data['raised_by_role'] = 'trainee' if getattr(user, 'role', '') == 'trainee' else 'employee'
        return Query.objects.create(**validated_data)

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model=Subject
        fields="__all__"

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model=Lesson
        fields="__all__"

class ContentStartSerializer(serializers.Serializer):
    content_viewed = serializers.CharField(max_length=255)  # Content identifier (e.g., lesson ID)
    start_time = serializers.DateTimeField()  # ISO 8601 format date/time string

class ContentEndSerializer(serializers.Serializer):
    content_viewed = serializers.CharField(max_length=255)  # Content identifier (e.g., lesson ID)
    end_time = serializers.DateTimeField()  # ISO 8601 format date/time string


class TrainerNotificationRequestSerializer(serializers.Serializer):
    subject = serializers.CharField(required=False, allow_blank=True, default="Notification")
    message = serializers.CharField()
    link = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    notification_type = serializers.ChoiceField(
        choices=[c[0] for c in Notification._meta.get_field('notification_type').choices],
        default='info'
    )
    mode = serializers.ChoiceField(choices=['individual', 'group'])
    audience = serializers.ChoiceField(choices=['employee', 'trainee', 'both'], default='employee')

    # individual mode
    usernames = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    # group mode (adjust to your domain)
    department = serializers.CharField(required=False, allow_blank=True)   # for employees


class NotificationItemSerializer(serializers.ModelSerializer):
    sent_by = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'subject', 'message', 'link', 'notification_type', 'created_at', 'sent_by']

    def get_sent_by(self, obj):
        return getattr(obj.sent_by, 'username', None)


class NotificationReceiptSerializer(serializers.ModelSerializer):
    notification = NotificationItemSerializer()

    class Meta:
        model = NotificationReceipt
        fields = ['id', 'notification', 'is_read', 'read_at', 'delivered_at']

class ActiveQuizListSerializer(serializers.ModelSerializer):
    quiz_id = serializers.IntegerField(source="id", read_only=True)
    has_attempted = serializers.BooleanField(read_only=True)
    ends_in_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            "quiz_id",
            "quiz_name",
            "quiz_type",
            "start_date",
            "end_date",
            "has_attempted",
            "ends_in_seconds",
        ]

    def get_ends_in_seconds(self, obj):
        from django.utils.timezone import now
        remaining = (obj.end_date - now()).total_seconds()
        return int(remaining) if remaining > 0 else 0
    
class SentNotificationSerializer(serializers.ModelSerializer):
    recipients_count = serializers.IntegerField(read_only=True)
    sent_by_username = serializers.CharField(source="sent_by.username", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "subject",
            "message",
            "link",
            "notification_type",
            "sent_by_username",
            "recipients_count",
            # include any timestamp your model has; if you only have "created_at" keep that
            "created_at",
        ]
        read_only_fields = fields


class LessonCompletionSerializer(serializers.Serializer):
    lesson_title = serializers.CharField(source='lesson.name')
    completed_at = serializers.DateTimeField()
    completed = serializers.BooleanField()

class TrainingReportSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField(max_length=150)
    name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    role = serializers.CharField(max_length=50)
    employee_id = serializers.CharField(max_length=50, allow_null=True, required=False)
    department = serializers.CharField(max_length=100, allow_null=True, required=False)
    designation = serializers.CharField(max_length=100, allow_null=True, required=False)
    trainer_name = serializers.CharField(max_length=150, allow_null=True, required=False)
    completed_lessons = LessonCompletionSerializer(many=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = None
        if instance.get('role') == 'trainee':
            profile = TraineeProfile.objects.filter(user_id=instance.get('user_id')).first()
        elif instance.get('role') == 'employee':
            profile = EmployeeProfile.objects.filter(user_id=instance.get('user_id')).first()
        if profile:
            data['name'] = profile.name if profile.name else data.get('name', "N/A")
            data['employee_id'] = profile.employee_id if profile.employee_id else data.get('employee_id', "N/A")
            data['department'] = profile.department if profile.department else data.get('department', "N/A")
            data['designation'] = profile.designation if profile.designation else data.get('designation', "N/A")
            if hasattr(profile, 'trainer'):
                trainer = profile.trainer
                # Use username as fallback, or combine first_name and last_name if available
                data['trainer_name'] = trainer.username if trainer else data.get('trainer_name', "N/A")
                # Uncomment the following line if you have first_name and last_name in CustomUser
                # data['trainer_name'] = f"{trainer.first_name} {trainer.last_name}" if trainer and trainer.first_name and trainer.last_name else data.get('trainer_name', "N/A")
        return data
    
class ActiveUserSerializer(serializers.ModelSerializer):
    profile_type = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'full_name', 'email', 'profile_type', 'department']

    def get_profile_type(self, obj):
        if hasattr(obj, 'traineeprofile') and obj.trainee_profile:
            return 'Trainee'
        elif hasattr(obj, 'employeeprofile') and obj.employee_profile:
            return 'Employee'
        return 'Unknown'

    def get_department(self, obj):
        if hasattr(obj, 'trainee_profile') and obj.trainee_profile:
            return obj.trainee_profile.department
        elif hasattr(obj, 'employee_profile') and obj.employee_profile:
            return obj.employee_profile.department
        return None

    def get_full_name(self, obj):
        return obj.get_full_name() or f"{obj.first_name} {obj.last_name}".strip()
    
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        help_text="The email address of the user requesting a password reset."
    )

    def validate_email(self, value):
        if not CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email does not exist.")
        return value