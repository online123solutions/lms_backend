from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    CustomUser, TraineeProfile, EmployeeProfile, TrainerProfile,AdminProfile,Courses, CourseLesson,Macroplanner,Microplanner,Assessment, AssessmentReport,EvaluationRemark
    ,TrainingReport,UserLoginActivity,Query,QueryResponse,Subject,Lesson,Notification,NotificationReceipt,SOP,StandardLibraryItem,
    TrainerLessonProgress,TraineeFeedback,TraineeTaskSubmission
)
from django.contrib.auth import authenticate
from quiz.serializers import ResultSerializer
from django.urls import reverse
from quiz.models import Quiz,Result
from urllib.parse import urljoin
from django.conf import settings
from django.db import IntegrityError
from .utils import get_trainer_profile

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
        fields = [
            'user', 'name', 'employee_id', 'department',
            'designation', 'expertise', 'profile_picture',
        ]
        # Nothing else needed; keep profile_picture writable

    def to_representation(self, instance):
        """
        Keep your normal representation but ensure profile_picture
        is an ABSOLUTE URL in responses.
        """
        data = super().to_representation(instance)
        request = self.context.get("request")

        # instance.profile_picture may be a FileField/ImageField or empty
        pic = getattr(instance, "profile_picture", None)
        try:
            # .url gives something like "/media/trainer_profiles/ablox.png"
            url = pic.url if pic else ""
        except Exception:
            url = ""

        if url and request is not None:
            data["profile_picture"] = request.build_absolute_uri(url)
        else:
            # If no request in context, leave it as relative or blank
            data["profile_picture"] = url or ""

        return data

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

        profile_fields = ['name','employee_id','department','designation','expertise','profile_picture']
        profile_data = {k: v for k, v in validated_data.items() if k in profile_fields}

        profile, created = TrainerProfile.objects.get_or_create(user=user, defaults=profile_data)
        if not created:
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()
        return profile

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user_serializer = CustomUserSerializer(instance=instance.user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            user_serializer.save()

        profile_fields = ['name','employee_id','department','designation','expertise','profile_picture']
        for key, value in validated_data.items():
            if key in profile_fields:
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
    db_id = serializers.IntegerField(source="id", read_only=True)
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
            'db_id',
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
        fields = ['id','week', 'duration', 'month', 'department', 'module','mode','role']


class MicroplannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Microplanner
        fields = ['id', 'month', 'week', 'days','department', 'no_of_sessions', 'name_of_topic','mode','role']


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
    # Lesson has "name", not "title"
    lesson_title = serializers.CharField(source='lesson.name', allow_null=True, required=False)
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
            data['name'] = profile.name or data.get('name', "N/A")
            data['employee_id'] = getattr(profile, 'employee_id', None) or data.get('employee_id', "N/A")
            data['department'] = getattr(profile, 'department', None) or data.get('department', "N/A")
            data['designation'] = getattr(profile, 'designation', None) or data.get('designation', "N/A")
            # safe nested getattr for trainer name
            trainer = getattr(profile, 'trainer', None)
            data['trainer_name'] = getattr(trainer, 'name', None) or getattr(trainer, 'username', None) or data.get('trainer_name', "N/A")
        return data
    

class ActiveUserSerializer(serializers.ModelSerializer):
    profile_type = serializers.SerializerMethodField()
    department   = serializers.SerializerMethodField()
    full_name    = serializers.SerializerMethodField()

    class Meta:
        model  = CustomUser
        fields = ["id", "username", "full_name", "email", "profile_type", "department"]

    def _profiles(self, obj):
        """Helper to avoid repeating getattr calls."""
        tp = getattr(obj, "trainee_profile", None)
        ep = getattr(obj, "employee_profile", None)
        return tp, ep

    def get_profile_type(self, obj):
        tp, ep = self._profiles(obj)
        if tp is not None:
            return "Trainee"
        if ep is not None:
            return "Employee"
        return "Unknown"

    def get_department(self, obj):
        tp, ep = self._profiles(obj)
        if tp and getattr(tp, "department", None):
            return tp.department
        if ep and getattr(ep, "department", None):
            return ep.department
        return ""

    def get_full_name(self, obj):
        tp, ep = self._profiles(obj)

        # Priority: profile.name → Django's full name → first/last → username
        name = (
            (getattr(tp, "name", "") or "").strip()
            or (getattr(ep, "name", "") or "").strip()
            or (getattr(obj, "get_full_name", lambda: "")() or "").strip()
            or " ".join(filter(None, [getattr(obj, "first_name", ""), getattr(obj, "last_name", "")])).strip()
        )
        return name or obj.username
    
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        help_text="The email address of the user requesting a password reset."
    )

    def validate_email(self, value):
        if not CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email does not exist.")
        return value
    

class SOPSerializer(serializers.ModelSerializer):
    usernames = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False,
        help_text="For INDIVIDUAL, list of usernames."
    )

    class Meta:
        model = SOP
        fields = [
            "id","title","note","recipient_type",
            "department","target_role",
            "recipients","usernames",
            "file","created_by","created_at",
        ]
        read_only_fields = ("created_by","created_at")
        extra_kwargs = {"recipients": {"required": False}}

    def validate(self, attrs):
        rtype = attrs.get("recipient_type", getattr(self.instance, "recipient_type", None))
        if rtype == "GROUP":
            dept = attrs.get("department", getattr(self.instance, "department", ""))
            role = attrs.get("target_role", getattr(self.instance, "target_role", ""))
            if not dept and not role:
                raise serializers.ValidationError("For GROUP, select department and/or role.")
        else:
            if not attrs.get("usernames") and not attrs.get("recipients"):
                raise serializers.ValidationError("For INDIVIDUAL, provide usernames or recipients.")
        return attrs

    def create(self, validated_data):
        usernames = validated_data.pop("usernames", [])
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user

        sop = super().create(validated_data)

        if sop.recipient_type == "INDIVIDUAL":
            if usernames:
                users = CustomUser.objects.filter(username__in=usernames)
                sop.recipients.set(users)
        # GROUP recipients are matched dynamically in the list views
        return sop
    
class TagsField(serializers.Field):
    """
    Accepts either:
      - ["policy", "onboarding"]  (list of strings)
      - "policy, onboarding"      (comma-separated string)
    Stores as a list (JSONField on the model).
    """
    def to_representation(self, value):
        # ensure we always expose a list
        return list(value or [])

    def to_internal_value(self, data):
        if data is None:
            return []
        if isinstance(data, (list, tuple)):
            try:
                return [str(x).strip() for x in data if str(x).strip()]
            except Exception:
                raise serializers.ValidationError("tags must be strings.")
        if isinstance(data, str):
            return [s.strip() for s in data.split(",") if s.strip()]
        raise serializers.ValidationError("tags must be a list of strings or a comma-separated string.")


class StandardLibraryItemSerializer(serializers.ModelSerializer):
    # Optional: flexible tags input
    tags = TagsField(required=False)

    class Meta:
        model = StandardLibraryItem
        fields = [
            "id", "title", "note",
            "department", "target_role",
            "file", "tags", "is_active",
            "created_by", "created_at",
        ]
        read_only_fields = ("created_by", "created_at")

    def validate(self, attrs):
        """
        Library items can be global (no department/role),
        or targeted by department and/or role.
        No extra checks needed unless you want to enforce at least one.
        """
        # Example if you ever want to force at least one target:
        # if not attrs.get("department") and not attrs.get("target_role"):
        #     raise serializers.ValidationError("Provide department and/or target_role, or leave both blank for global.")
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        # ensure tags key exists (JSONField default is [], but be explicit)
        validated_data.setdefault("tags", [])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # keep created_by unchanged
        validated_data.pop("created_by", None)
        return super().update(instance, validated_data)
    

class SubjectProgressSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    subject_name = serializers.CharField()
    total_lessons = serializers.IntegerField()
    completed_lessons = serializers.IntegerField()
    pending_lessons = serializers.IntegerField()
    progress_pct = serializers.FloatField()
    last_completed_at = serializers.DateTimeField(allow_null=True)

class TraineeProgressSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    name = serializers.CharField()
    totals = serializers.DictField()
    subjects = SubjectProgressSerializer(many=True)

class EmployeeProgressSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    name = serializers.CharField()
    totals = serializers.DictField()
    subjects = serializers.ListField(child=serializers.DictField())

class TrainerLessonProgressWriteSerializer(serializers.ModelSerializer):
    action = serializers.ChoiceField(choices=[("start","start"),("complete","complete")], required=False)

    class Meta:
        model = TrainerLessonProgress
        fields = ["id", "lesson", "status", "percent", "action"]

    def validate(self, attrs):
        request = self.context["request"]
        trainer = get_trainer_profile(request.user)
        if not trainer:
            raise serializers.ValidationError("Trainer profile not found for user.")
        # Optional: ensure lesson belongs to same department
        lesson = attrs.get("lesson") or getattr(self.instance, "lesson", None)
        if lesson and lesson.course.department != trainer.department:
            raise serializers.ValidationError("You cannot update lessons outside your department.")
        return attrs

    def create(self, validated_data):
        action = validated_data.pop("action", None)
        trainer = get_trainer_profile(self.context["request"].user)
        obj, _ = TrainerLessonProgress.objects.get_or_create(
            trainer=trainer, lesson=validated_data["lesson"]
        )
        for k, v in validated_data.items():
            setattr(obj, k, v)
        if action == "start":
            obj.mark_started()
        elif action == "complete":
            obj.mark_started()
            obj.mark_completed()
        obj.save()
        return obj

    def update(self, instance, validated_data):
        action = validated_data.pop("action", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if action == "start":
            instance.mark_started()
        elif action == "complete":
            instance.mark_started()
            instance.mark_completed()
        instance.save()
        return instance



class CourseProgressSummarySerializer(serializers.Serializer):
    """
    Read-only summary per course (subject) for the current trainer.
    """
    course_id = serializers.IntegerField()
    course_title = serializers.CharField()
    total_lessons = serializers.IntegerField()
    completed_lessons = serializers.IntegerField()
    completion_percent = serializers.IntegerField()

class TrainerLessonProgressReadSerializer(serializers.ModelSerializer):
    # Flattened, read-only fields pulled from related models
    lesson_id    = serializers.IntegerField(source="lesson.id", read_only=True)
    lesson_name  = serializers.CharField(source="lesson.lesson_name", read_only=True)
    course_id    = serializers.IntegerField(source="lesson.course.id", read_only=True)
    course_code  = serializers.CharField(source="lesson.course.course_id", read_only=True)   # your unique string
    course_name  = serializers.CharField(source="lesson.course.course_name", read_only=True)

    class Meta:
        model  = TrainerLessonProgress
        fields = [
            "id",
            "lesson_id", "lesson_name",
            "course_id", "course_code", "course_name",
            "status", "percent",
            "started_at", "completed_at", "last_accessed_at",
        ]
        read_only_fields = fields  # this entire serializer is read-only


class AdminTrainerLessonProgressSerializer(serializers.ModelSerializer):
    # Trainer meta
    trainer_user_id   = serializers.IntegerField(source="trainer.user.id", read_only=True)
    trainer_username  = serializers.CharField(source="trainer.user.username", read_only=True)
    trainer_name      = serializers.SerializerMethodField()
    department        = serializers.CharField(source="trainer.department", read_only=True)

    # Course meta (both numeric PK and your string code)
    course_id         = serializers.IntegerField(source="lesson.course.id", read_only=True)          # numeric PK
    course_code       = serializers.CharField(source="lesson.course.course_id", read_only=True)      # your string code
    course_name       = serializers.CharField(source="lesson.course.course_name", read_only=True)

    # Lesson meta
    lesson_id         = serializers.IntegerField(source="lesson.id", read_only=True)
    lesson_name       = serializers.CharField(source="lesson.lesson_name", read_only=True)

    class Meta:
        model = TrainerLessonProgress
        fields = [
            "id",

            # trainer
            "trainer_id",
            "trainer_user_id",
            "trainer_username",
            "trainer_name",
            "department",

            # course
            "course_id",
            "course_code",
            "course_name",

            # lesson
            "lesson_id",
            "lesson_name",

            # progress
            "status",
            "percent",
            "started_at",
            "completed_at",
            "last_accessed_at",
        ]

    def get_trainer_name(self, obj):
        u = getattr(obj.trainer, "user", None)
        if u and hasattr(u, "get_full_name"):
            full = (u.get_full_name() or "").strip()
            if full:
                return full
        return getattr(u, "username", "") or f"trainer-{obj.trainer_id}"

class AdminCourseProgressRowSerializer(serializers.Serializer):
    trainer_id = serializers.IntegerField()
    trainer_username = serializers.CharField()
    trainer_name = serializers.CharField()
    trainer_department = serializers.CharField()

    course_pk = serializers.IntegerField()
    course_id = serializers.CharField()     # your string identifier
    course_name = serializers.CharField()

    total_lessons = serializers.IntegerField()
    completed_lessons = serializers.IntegerField()
    completion_percent = serializers.IntegerField()


class AdminTrainerSummaryRowSerializer(serializers.Serializer):
    """
    Row serializer for a trainer’s overall summary (across courses).
    """
    trainer_id = serializers.IntegerField()
    trainer_username = serializers.CharField()
    trainer_name = serializers.CharField()
    department = serializers.CharField()
    total_lessons = serializers.IntegerField()
    completed_lessons = serializers.IntegerField()
    completion_percent = serializers.IntegerField()

# serializers.py
class InboxNotificationSerializer(serializers.ModelSerializer):
    sent_by = serializers.SerializerMethodField()
    read_at = serializers.DateTimeField(source='my_read_at', allow_null=True)

    def get_sent_by(self, obj):
        u = getattr(obj, "sent_by", None)
        if not u:
            return None
        return {"username": u.username, "role": getattr(u, "role", None)}

    class Meta:
        model = Notification
        fields = ("id", "subject", "message", "link", "created_at", "sent_by", "read_at")

class TraineeFeedbackSerializer(serializers.ModelSerializer):
    trainee_id = serializers.ReadOnlyField(source='trainee.id')
    trainee_username = serializers.ReadOnlyField(source='trainee.username')

    class Meta:
        model = TraineeFeedback
        fields = [
            'id',
            'trainee_id',
            'trainee_username',
            'communication',
            'subject_knowledge',
            'mentorship',
            'custom_feedback',
            'created_at'
        ]

ADMIN_ROLE_CHOICES = ["trainer", "employee", "trainee"]

class AdminNotificationRequestSerializer(serializers.Serializer):
    # Core fields
    subject = serializers.CharField(required=False, allow_blank=True, default="Notification")
    message = serializers.CharField()
    link = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    notification_type = serializers.ChoiceField(
        choices=[c[0] for c in Notification._meta.get_field("notification_type").choices],
        default="info"
    )

    # Modes
    mode = serializers.ChoiceField(choices=["individual", "group"])

    # Individual mode
    usernames = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )

    # Group mode — preferred modern way
    audience_roles = serializers.ListField(
        child=serializers.ChoiceField(choices=ADMIN_ROLE_CHOICES),
        required=False,
        allow_empty=False
    )

    # Group mode — legacy back-compat (optional)
    # Accepts: employee | trainee | trainer | both | all
    audience = serializers.ChoiceField(
        choices=["employee", "trainee", "trainer", "both", "all"],
        required=False
    )

    # Optional scoping by departments (applies to employee and trainer roles)
    # e.g., ["Robotics", "AI Lab"]
    departments = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )

    def validate(self, attrs):
        mode = attrs.get("mode")
        subject = (attrs.get("subject") or "Notification").strip()
        message = (attrs.get("message") or "").strip()
        link = (attrs.get("link") or None) or None

        if not message:
            raise serializers.ValidationError({"message": "Message is required."})

        normalized_roles = None

        if mode == "individual":
            usernames = list({
                (u or "").strip()
                for u in (attrs.get("usernames") or [])
                if (u or "").strip()
            })
            if not usernames:
                raise serializers.ValidationError({"usernames": "Provide at least one username for individual mode."})
            attrs["usernames"] = usernames
            normalized_roles = []  # not used in individual mode, but keep a consistent shape

        elif mode == "group":
            audience_roles = attrs.get("audience_roles")
            legacy = (attrs.get("audience") or "").strip().lower()

            if audience_roles:
                normalized_roles = sorted(set(map(str.lower, audience_roles)))
            elif legacy:
                if legacy == "all":
                    normalized_roles = ["trainer", "employee", "trainee"]
                elif legacy == "both":
                    normalized_roles = ["employee", "trainee"]
                elif legacy in ADMIN_ROLE_CHOICES:
                    normalized_roles = [legacy]
                else:
                    raise serializers.ValidationError({"audience": "Invalid legacy audience."})
            else:
                raise serializers.ValidationError({"audience_roles": "Provide audience_roles or legacy audience for group mode."})

            # Validate roles
            invalid = [r for r in normalized_roles if r not in ADMIN_ROLE_CHOICES]
            if invalid:
                raise serializers.ValidationError({"audience_roles": f"Invalid roles: {invalid}"})

            if not normalized_roles:
                raise serializers.ValidationError({"audience_roles": "At least one role must be selected."})
        else:
            raise serializers.ValidationError({"mode": "Invalid mode. Use 'individual' or 'group'."})

        # Normalize departments (optional)
        depts = [
            (d or "").strip()
            for d in (attrs.get("departments") or [])
            if (d or "").strip()
        ]
        attrs["departments"] = list(dict.fromkeys(depts)) or None

        # Final normalized fields
        attrs["subject"] = subject
        attrs["message"] = message
        attrs["link"] = link or None
        attrs["audience"] = normalized_roles           # always a list
        attrs["audience_roles"] = normalized_roles     # keep both for convenience

        return attrs
    

class TraineeTaskSubmissionSerializer(serializers.ModelSerializer):
    trainee_username = serializers.SerializerMethodField(read_only=True)
    reviewed_by_username = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TraineeTaskSubmission
        fields = [
            "id",
            "trainee_username",
            "department",
            "text",
            "file",
            "submitted_at",
            "status",
            "marks",
            "feedback",
            "reviewed_by_username",
            "reviewed_at",
            "review_file",
        ]
        read_only_fields = [
            "submitted_at", "status", "marks", "feedback",
            "reviewed_by_username", "reviewed_at", "review_file",
        ]

    def get_trainee_username(self, obj):
        return getattr(obj.trainee, "username", None)

    def get_reviewed_by_username(self, obj):
        return getattr(obj.reviewed_by, "username", None)

    def validate(self, attrs):
        text = (attrs.get("text") or "").strip()
        file_ = attrs.get("file")
        if not text and not file_:
            raise serializers.ValidationError("Provide either text or file (or both).")
        return attrs
    
class TraineeTaskReviewSerializer(serializers.ModelSerializer):
    """Used only by trainers/admin to review/score a submission."""
    class Meta:
        model = TraineeTaskSubmission
        fields = ["marks", "feedback", "review_file"]
        extra_kwargs = {
            "marks": {"required": True},
            "feedback": {"required": False},
            "review_file": {"required": False},
        }

    def validate_marks(self, v):
        # Typical 0..100 range; tweak if you need a different range
        if v is None:
            return v
        if v < 0 or v > 100:
            raise serializers.ValidationError("Marks must be between 0 and 100.")
        return v