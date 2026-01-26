from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from rest_framework.response import Response
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.db.models.functions import TruncDate
from user.models import (
    AdminProfile,TraineeProfile, CustomUser,Courses,CourseLesson,Microplanner,Macroplanner,Assessment,AssessmentReport,EvaluationRemark,TrainingReport,UserLoginActivity,QueryResponse,
    Query,EmployeeProfile,Notification,NotificationReceipt,TraineeLessonCompletion,EmployeeLessonCompletion,AdminProfile,TrainerProfile,
    TrainerLessonProgress,TraineeFeedback,Subject,Lesson
)
from user.serializers import (
    TrainerSerializer,CourseSerializer, CourseLessonSerializer, MacroplannerSerializer, MicroplannerSerializer,AssessmentSerializer,AssessmentReportSerializer,
    EvaluationRemarkSerializer,TrainingReportSerializer,UserLoginActivitySerializer,QueryResponseSerializer,QuerySerializer,
    TrainerNotificationRequestSerializer,SentNotificationSerializer,ActiveUserSerializer,AdminSerializer,AdminTrainerSummaryRowSerializer,
    AdminTrainerLessonProgressSerializer,AdminCourseProgressRowSerializer,TraineeFeedbackSerializer,AdminNotificationRequestSerializer,
    InboxNotificationSerializer,SubjectSerializer,LessonSerializer
)
from rest_framework.generics import ListCreateAPIView,RetrieveUpdateAPIView, ListAPIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets,generics,status,permissions
from rest_framework.exceptions import PermissionDenied
from .tasks import send_notification_email, send_push_notification
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from .utils import get_active_users
from django.db import transaction
from datetime import date
from django.db.models import Q, Count
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import FieldDoesNotExist
from quiz.models import Quiz
from .utils import get_active_users
from django.db.models import Case, When, Value, CharField, F, Q,OuterRef,Subquery,Exists,DateTimeField
from .views import BaseSOPListView,BaseSLListView
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ObjectDoesNotExist

class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            admin_obj = AdminProfile.objects.get(user=request.user)
        except AdminProfile.DoesNotExist:
            return Response({"error": "Admin profile not found."}, status=404)

        # Profile data
        profile_data = AdminSerializer(admin_obj).data

        # All users across all profile types
        all_users = CustomUser.objects.all()
        total_users = all_users.count()
        users_data = ActiveUserSerializer(all_users, many=True).data

        # Department-wise data (aggregating departments from all profile models)
        department_data = []
        # Get unique departments from all profile models
        departments = set()
        for profile_model in [AdminProfile, TrainerProfile, EmployeeProfile, TraineeProfile]:
            dept_values = profile_model.objects.values('department').distinct()
            departments.update(dept['department'] for dept in dept_values if dept['department'])

        for dept_name in departments:
            # Users in this department (checking all profile types)
            dept_users = CustomUser.objects.filter(
                Q(admin_profile__department=dept_name) |
                Q(trainer_profile__department=dept_name) |
                Q(employee_profile__department=dept_name) |
                Q(trainee_profile__department=dept_name)
            )
            dept_user_count = dept_users.count()

            # Courses in this department
            dept_courses = Courses.objects.filter(department=dept_name)
            dept_course_count = dept_courses.count()

            # Trainees in this department
            dept_trainees = CustomUser.objects.filter(
                trainee_profile__department=dept_name
            ).count()

            department_data.append({
                "department": dept_name,
                "user_count": dept_user_count,
                "course_count": dept_course_count,
                "trainee_count": dept_trainees,
                "courses": CourseSerializer(dept_courses, many=True).data
            })

        # Overall course statistics
        all_courses = Courses.objects.all()
        total_courses = all_courses.count()
        course_status_counts = all_courses.values('is_approved').annotate(
            count=Count('is_approved')
        )

        # Active users across all departments
        active_users = CustomUser.objects.filter(is_active=True)
        active_count = active_users.count()
        active_users_data = ActiveUserSerializer(active_users, many=True).data

        return Response({
            "profile": profile_data,
            "total_users": total_users,
            "users": users_data,
            "total_courses": total_courses,
            "course_status_counts": list(course_status_counts),
            "departments": department_data,
            "active_users_count": active_count,
            "active_users": active_users_data
        }, status=200)


class AdminCourseView(ListCreateAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def get_queryset(self):
        try:
            trainer = AdminProfile.objects.get(user=self.request.user)
            return Courses.objects.filter(display_on_frontend=True)
        except AdminProfile.DoesNotExist:
            return Courses.objects.none()


    def perform_create(self, serializer):
        trainer = get_object_or_404(AdminProfile, user=self.request.user)
        serializer.save(created_by=self.request.user, department=trainer.department)


class AdminCourseLessonView(ListCreateAPIView):
    serializer_class = CourseLessonSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def get_queryset(self):
        trainer = get_object_or_404(AdminProfile, user=self.request.user)
        return CourseLesson.objects.filter(
            display_on_frontend=True
        )

    def perform_create(self, serializer):
        trainer = get_object_or_404(AdminProfile, user=self.request.user)
        serializer.save(created_by=self.request.user)


class AdminMacroplannerViewSet(viewsets.ModelViewSet):
    serializer_class = MacroplannerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            # Verify the user is an admin
            AdminProfile.objects.get(user=self.request.user)
            # Return all Macroplanner entries, not restricted to admin's department
            return Macroplanner.objects.all()
        except AdminProfile.DoesNotExist:
            raise PermissionDenied("Only admins can access macroplanners.")

    def perform_create(self, serializer):
        try:
            # Verify the user is an admin
            AdminProfile.objects.get(user=self.request.user)
            # Save with department from request data
            serializer.save()
        except AdminProfile.DoesNotExist:
            raise PermissionDenied("Only admins can create macroplanners.")

    def perform_update(self, serializer):
        try:
            # Verify the user is an admin
            AdminProfile.objects.get(user=self.request.user)
            # Save with department from request data
            serializer.save()
        except AdminProfile.DoesNotExist:
            raise PermissionDenied("Only admins can update macroplanners.")


class AdminMicroplannerViewSet(viewsets.ModelViewSet):
    serializer_class = MicroplannerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            # Verify the user is an admin
            AdminProfile.objects.get(user=self.request.user)
            # Return all Microplanner entries, not restricted to admin's department
            return Microplanner.objects.all()
        except AdminProfile.DoesNotExist:
            raise PermissionDenied("Only admins can access microplanners.")

    def perform_create(self, serializer):
        try:
            # Verify the user is an admin
            AdminProfile.objects.get(user=self.request.user)
            # Save with department from request data
            serializer.save()
        except AdminProfile.DoesNotExist:
            raise PermissionDenied("Only admins can create microplanners.")

    def perform_update(self, serializer):
        try:
            # Verify the user is an admin
            AdminProfile.objects.get(user=self.request.user)
            # Save with department from request data
            serializer.save()
        except AdminProfile.DoesNotExist:
            raise PermissionDenied("Only admins can update microplanners.")


class AssessmentListCreateView(ListCreateAPIView):
    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Assessment.objects.filter(assigned_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)


class AdminAssessmentReportView(APIView):
    permission_classes = [IsAuthenticated]

    # ---------- helpers ----------
    def _truthy(self, v):
        return str(v).lower() in {"1", "true", "yes", "on"}

    REPORT_TYPE_KEYS = {
        "homework",
        "pre-assessment",
        "post-assessment",
        "daily-quiz",
        "weekly-quiz",
        "monthly-quiz",
        "final-exam",
    }

    def _derive_report_type(self, quiz):
        """
        Map Quiz.quiz_type -> AssessmentReport.report_type (must be one of REPORT_TYPE_KEYS).
        Falls back to 'daily-quiz' if unknown.
        """
        raw = (getattr(quiz, "quiz_type", "") or "").strip().lower()
        norm = raw.replace("_", "-").replace(" ", "-")
        return norm if norm in self.REPORT_TYPE_KEYS else "daily-quiz"

    def _resolve_quiz_trainer_fk(self):
        """Find FK on Quiz pointing to User (assigned_by/created_by/trainer/owner or first FK to User)."""
        for name in ("assigned_by", "created_by", "trainer", "owner"):
            try:
                f = Quiz._meta.get_field(name)
                if getattr(f, "related_model", None) is CustomUser:
                    return name
            except FieldDoesNotExist:
                continue
        # fallback: first FK to User
        for f in Quiz._meta.get_fields():
            if getattr(f, "is_relation", False) and getattr(f, "many_to_one", False):
                if getattr(f, "related_model", None) is CustomUser:
                    return f.name
        return None

    def _trainer_quizzes_qs(self, user):
        fk = self._resolve_quiz_trainer_fk()
        if not fk:
            return Quiz.objects.none()
        return Quiz.objects.filter(**{fk: user})

    def _ensure_reports_for_quizzes(self, quizzes, audiences=("trainee", "employee")):
        """Create missing AssessmentReport rows for quizzes & audiences, then compute metrics once."""
        has_audience = any(f.name == "audience" for f in AssessmentReport._meta.get_fields())
        if not has_audience:
            audiences = (None,)

        if has_audience:
            existing = set(
                AssessmentReport.objects.filter(quiz__in=quizzes)
                .values_list("quiz_id", "audience")
            )
        else:
            existing = set(
                AssessmentReport.objects.filter(quiz__in=quizzes)
                .values_list("quiz_id", flat=True)
            )

        to_create = []
        for q in quizzes:
            rt = self._derive_report_type(q)  # <-- derive from quiz.quiz_type
            for aud in audiences:
                key = (q.id, aud) if has_audience else q.id
                if key in existing:
                    continue
                kwargs = {"quiz": q, "report_type": rt}
                if has_audience:
                    kwargs["audience"] = aud
                to_create.append(AssessmentReport(**kwargs))

        if to_create:
            AssessmentReport.objects.bulk_create(to_create, ignore_conflicts=True)

        # refresh metrics once
        for r in AssessmentReport.objects.filter(quiz__in=quizzes):
            try:
                r.update_report()
            except Exception:
                continue

    # ---------- GET ----------
    @swagger_auto_schema(
        operation_description="""
        List assessment reports.

        Modes:
        • With quiz_id: return report(s) for that quiz (no ownership filter). Defaults: autocreate+refresh = true.
        • Without quiz_id: list reports for the current trainer’s quizzes.

        Query:
        - quiz_id (int)
        - audience: trainee | employee
        - refresh: 1/true/yes (default TRUE when quiz_id provided)
        - autocreate: 1/true/yes (default TRUE when quiz_id provided)
        """,
        manual_parameters=[
            openapi.Parameter('quiz_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('audience', openapi.IN_QUERY, type=openapi.TYPE_STRING, enum=["trainee","employee"]),
            openapi.Parameter('refresh', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('autocreate', openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: AssessmentReportSerializer(many=True)},
    )
    def get(self, request):
        quiz_id = request.query_params.get("quiz_id")
        audience = (request.query_params.get("audience") or "").strip().lower() or None
        has_audience = any(f.name == "audience" for f in AssessmentReport._meta.get_fields())

        # ----- Direct quiz mode -----
        if quiz_id:
            quiz = get_object_or_404(Quiz, pk=quiz_id)

            # default TRUE when quiz_id present unless explicitly disabled
            do_autocreate = self._truthy(request.query_params.get("autocreate")) or request.query_params.get("autocreate") is None
            do_refresh    = self._truthy(request.query_params.get("refresh"))    or request.query_params.get("refresh")    is None

            if do_autocreate:
                if has_audience:
                    auds = (audience,) if audience in {"trainee","employee"} else ("trainee","employee")
                else:
                    auds = (None,)
                self._ensure_reports_for_quizzes([quiz], audiences=auds)

            qs = AssessmentReport.objects.select_related("quiz").filter(quiz=quiz)
            if has_audience and audience in {"trainee","employee"}:
                qs = qs.filter(audience=audience)

            if do_refresh:
                for r in qs:
                    try:
                        r.update_report()
                    except Exception:
                        pass

            ser = AssessmentReportSerializer(qs.order_by("-last_updated", "-id"), many=True, context={"request": request})
            return Response(ser.data, status=200)

        # ----- List mode (trainer’s quizzes) -----
        quizzes = list(self._trainer_quizzes_qs(request.user).only("id", "department"))
        if not quizzes:
            return Response([], status=200)

        do_autocreate = self._truthy(request.query_params.get("autocreate"))
        do_refresh    = self._truthy(request.query_params.get("refresh"))

        if do_autocreate:
            self._ensure_reports_for_quizzes(quizzes)

        qs = AssessmentReport.objects.select_related("quiz").filter(quiz__in=quizzes)
        if has_audience and audience in {"trainee","employee"}:
            qs = qs.filter(audience=audience)

        if do_refresh:
            for r in qs:
                try:
                    r.update_report()
                except Exception:
                    pass

        ser = AssessmentReportSerializer(qs.order_by("-last_updated", "-id"), many=True, context={"request": request})
        return Response(ser.data, status=200)
    
class AssessmentReportUpdateView(RetrieveUpdateAPIView):
    queryset = AssessmentReport.objects.all()
    serializer_class = AssessmentReportSerializer
    permission_classes = [IsAuthenticated]

class EvaluationRemarkView(ListCreateAPIView):
    serializer_class = EvaluationRemarkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EvaluationRemark.objects.filter(trainer=self.request.user)

    def perform_create(self, serializer):
        serializer.save(trainer=self.request.user)
    
class AdminLMSEngagementView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserLoginActivitySerializer

    def get_queryset(self):
        # Collect usernames for ALL trainees and employees
        trainee_usernames = TraineeProfile.objects.all().values_list("user__username", flat=True)
        employee_usernames = EmployeeProfile.objects.all().values_list("user__username", flat=True)

        # Combine and deduplicate usernames
        usernames = list(set(list(trainee_usernames) + list(employee_usernames)))
        
        if not usernames:
            return UserLoginActivity.objects.none()

        # Filter login activities by usernames and order by login_datetime
        qs = UserLoginActivity.objects.filter(
            login_username__in=usernames
        ).order_by("-login_datetime")

        # Optional: filter by month ?month=YYYY-MM
        month = self.request.query_params.get("month")
        if month:
            try:
                year, mon = map(int, month.split("-"))
                start = date(year, mon, 1)
                end = date(year + (mon == 12), (mon % 12) + 1, 1)
                qs = qs.filter(login_datetime__gte=start, login_datetime__lt=end)
            except Exception:
                # Ignore bad month format (or raise ValidationError if preferred)
                pass

        return qs
    
class AdminRecentActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            admin_obj = AdminProfile.objects.get(user=request.user)
        except AdminProfile.DoesNotExist:
            raise NotFound(detail="Admin record not found for this user.")
        
        # Cache key (optional, retained for potential caching)
        cache_key = f"recent_activity_{admin_obj.pk}"

        try:
            # Collect usernames for ALL trainees and employees
            trainee_usernames = TraineeProfile.objects.all().values_list("user__username", flat=True)
            employee_usernames = EmployeeProfile.objects.all().values_list("user__username", flat=True)
            usernames = list(set(list(trainee_usernames) + list(employee_usernames)))

            # Get unique departments
            employee_depts = EmployeeProfile.objects.values_list("department", flat=True)
            trainee_depts = TraineeProfile.objects.values_list("department", flat=True)
            departments = list(set(list(employee_depts) + list(trainee_depts)))

            # Recent logins (last 5)
            recent_logins = UserLoginActivity.objects.filter(
                login_username__in=usernames,
                status='S'
            ).annotate(
                truncated_login_date=TruncDate("login_datetime")
            ).values(
                "login_username",
                login_date=F("truncated_login_date")
            ).order_by("-login_datetime")[:5]

            # Recent assessment submissions (last 5)
            recent_assessments = AssessmentReport.objects.filter(
                Q(audience='trainee') | Q(audience='employee'),
                quiz__department__in=departments
            ).annotate(
                truncated_submission_date=TruncDate("last_updated"),
                username=Case(
                    When(audience='trainee', then=F('quiz__created_by__username')),
                    When(audience='employee', then=F('quiz__created_by__username')),
                    default=Value('Unknown'),
                    output_field=CharField(),
                )
            ).values(
                "username",
                quiz_name=F("quiz__quiz_name"),
                submission_date=F("truncated_submission_date")
            ).order_by("-truncated_submission_date")[:5]

            # Recent lesson completions (last 5)
            employee_completions = EmployeeLessonCompletion.objects.filter(
                employee__user__username__in=usernames,
                completed=True
            ).annotate(
                truncated_completed_date=TruncDate("completed_at")
            ).values(
                username=F("employee__user__username"),
                lesson_name=F("lesson__name"),
                completed_date=F("truncated_completed_date")
            ).order_by("-completed_at")[:5]

            trainee_completions = TraineeLessonCompletion.objects.filter(
                trainee__user__username__in=usernames,
                completed=True
            ).annotate(
                truncated_completed_date=TruncDate("completed_at")
            ).values(
                username=F("trainee__user__username"),
                lesson_name=F("lesson__name"),
                completed_date=F("truncated_completed_date")
            ).order_by("-completed_at")[:5]

            recent_completions = sorted(
                list(employee_completions) + list(trainee_completions),
                key=lambda x: x["completed_date"] if x["completed_date"] else "0000-00-00",
                reverse=True
            )[:5]

            # Recent queries raised (last 5)
            recent_queries = Query.objects.filter(
                raised_by__username__in=usernames
            ).annotate(
                truncated_created_date=TruncDate("created_at")
            ).values(
                username=F("raised_by__username"),
                # question=F("question"),
                created_date=F("truncated_created_date")
            ).order_by("-created_at")[:5]

            # Recent lesson plan/PPT uploads (last 5)
            recent_uploads = CourseLesson.objects.filter(
                created_by__username__in=TrainerProfile.objects.values_list("user__username", flat=True),
                # Q(lesson_plans__isnull=False) | Q(lesson_ppt__isnull=False)
            ).annotate(
                truncated_upload_date=TruncDate("created_at")
            ).values(
                "lesson_name",
                upload_date=F("truncated_upload_date")
            ).order_by("-created_at")[:5]

            response_data = {
                "recent_activity": {
                    "recent_logins": list(recent_logins),
                    "recent_homework_submissions": list(recent_assessments),
                    "recent_completions": list(recent_completions),
                    "recent_queries": list(recent_queries),
                    "recent_uploads": list(recent_uploads),
                }
            }

            return Response(response_data)

        except Exception as e:
            return Response({"error": f"Unexpected error: {str(e)}"}, status=500)

class TrainerQueryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Only trainers can see all queries
        queries = Query.objects.all()  # Get all queries for trainers
        serializer = QuerySerializer(queries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TrainerQueryResponseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, query_id):
        query = get_object_or_404(Query, id=query_id)

        # ✅ If unassigned, auto-assign to current trainer
        if query.assigned_trainer_id is None:
            query.assigned_trainer = request.user
            query.save(update_fields=["assigned_trainer"])
        # ✅ If assigned to someone else, block
        elif request.user != query.assigned_trainer:
            return Response({"error": "You are not authorized to respond to this query."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = QueryResponseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(query=query, responder=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TrainerAssignTrainerAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, query_id):
        query = get_object_or_404(Query, id=query_id)

        # ✅ Allow trainers/admins to assign (not only the raiser)
        is_trainer = getattr(request.user, "role", "") == "trainer"
        if not (request.user.is_staff or is_trainer):
            return Response({"error": "Only trainers/admins can assign."}, status=status.HTTP_403_FORBIDDEN)

        trainer_val = request.data.get("assigned_trainer")
        if not trainer_val:
            return Response({"error": "Trainer not specified."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Resolve to actual User (supports id or username)
        try:
            if str(trainer_val).isdigit():
                new_trainer = CustomUser.objects.get(id=int(trainer_val))
            else:
                new_trainer = CustomUser.objects.get(username=str(trainer_val))
        except CustomUser.DoesNotExist:
            return Response({"error": "Trainer user not found."}, status=status.HTTP_400_BAD_REQUEST)

        query.assigned_trainer = new_trainer  # must be a FK
        query.save(update_fields=["assigned_trainer"])
        return Response(
            {"message": "Trainer assigned successfully.", "assigned_trainer_username": new_trainer.username},
            status=status.HTTP_200_OK,
        )

class SmallPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200

BULK_CHUNK = 2000  # tune to your DB

class TrainerNotifyView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        # Same auth gate as POST
        role = getattr(request.user, "role", None)
        if role != "trainer" and not request.user.is_staff:
            return Response({"error": "Only trainers can view their sent notifications."},
                            status=status.HTTP_403_FORBIDDEN)

        qs = (
            Notification.objects.filter(sent_by=request.user)
            .annotate(recipients_count=Count("notificationreceipt", distinct=True))
        )

        # --- Filters ---
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(subject__icontains=search)
                | Q(message__icontains=search)
                | Q(link__icontains=search)
            )

        date_from = (request.query_params.get("date_from") or "").strip()
        date_to = (request.query_params.get("date_to") or "").strip()
        # filter only if your Notification has created_at (adjust if different)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        qs = qs.order_by("-created_at", "-id")  # safe even if created_at ties

        paginator = SmallPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        ser = SentNotificationSerializer(page, many=True)
        return paginator.get_paginated_response(ser.data)


    @swagger_auto_schema(
        operation_description="""
        Send notifications (Trainer → Employees/Trainees).

        Modes:
        - individual: pass `usernames` (list of usernames; employees and/or trainees)
        - group:
            audience: employee | trainee | both
            department (optional, employees only; defaults to trainer's department if available)
        """,
        request_body=TrainerNotificationRequestSerializer,
        responses={200: openapi.Response("OK"), 400: "Bad Request", 403: "Forbidden", 404: "Not Found"}
    )
    def post(self, request):
        # ✅ Only trainers (or staff, if you allow) can send
        role = getattr(request.user, "role", None)
        if role != "trainer" and not request.user.is_staff:
            return Response({"error": "Only trainers can send notifications."}, status=status.HTTP_403_FORBIDDEN)

        ser = TrainerNotificationRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        subject    = data["subject"].strip()
        message    = data["message"].strip()
        link       = (data.get("link") or "").strip() or None
        notif_type = data["notification_type"]
        mode       = data["mode"]
        audience   = data["audience"]          # employee | trainee | both
        dept_arg   = (data.get("department") or "").strip() or None

        # Get trainer dept (fallback)
        trainer_dept = None
        try:
            tp = AdminProfile.objects.only("department").get(user=request.user)
            trainer_dept = tp.department
        except AdminProfile.DoesNotExist:
            pass

        # ---------- Build recipients ----------
        base_q = Q(is_active=True)
        role_q = Q()

        if mode == "individual":
            usernames = data.get("usernames") or []
            if not usernames:
                return Response({"error": "`usernames` is required for individual mode."}, status=400)

            # normalize + dedupe
            usernames = list({str(u).strip() for u in usernames if str(u).strip()})
            if not usernames:
                return Response({"error": "No valid usernames provided."}, status=400)

            # Optionally enforce audience subset:
            # if audience != "both":
            #     role_q = Q(role=("employee" if audience == "employee" else "trainee"))

            qs = CustomUser.objects.filter(base_q, Q(username__in=usernames)).only("id", "email", "role")
        elif mode == "group":
            if audience in ("employee", "both"):
                if dept_arg:
                    role_q |= Q(role="employee", employee_profile__department=dept_arg)
                elif trainer_dept:
                    role_q |= Q(role="employee", employee_profile__department=trainer_dept)
                else:
                    role_q |= Q(role="employee")

            if audience in ("trainee", "both"):
                role_q |= Q(role="trainee")

            if role_q.children == []:
                return Response({"error": "Invalid audience for group mode."}, status=400)

            qs = CustomUser.objects.filter(base_q & role_q).only("id", "email", "role")
        else:
            return Response({"error": "Invalid mode. Use 'individual' or 'group'."}, status=400)

        # Exclude sender & dedupe
        qs = qs.exclude(id=request.user.id).distinct()

        # Pull ids/emails without materializing full objects
        recipients = list(qs.values_list("id", "email", "role"))
        if not recipients:
            return Response({"error": "No matching recipients found."}, status=404)

        ids    = [r[0] for r in recipients]
        emails = [r[1] for r in recipients if r[1]]
        roles  = [r[2] for r in recipients]

        emp_count = sum(1 for r in roles if r == "employee")
        trn_count = sum(1 for r in roles if r == "trainee")

        # ---------- Write + side-effects ----------
        with transaction.atomic():
            notif = Notification.objects.create(
                subject=subject,
                message=message,
                link=link,
                notification_type=notif_type,
                sent_by=request.user,
            )

            # Bulk receipts in chunks (better on large sends)
            from itertools import islice
            def chunks(seq, n):
                it = iter(seq)
                while True:
                    batch = list(islice(it, n))
                    if not batch:
                        break
                    yield batch

            for batch_ids in chunks(ids, BULK_CHUNK):
                NotificationReceipt.objects.bulk_create(
                    [NotificationReceipt(notification=notif, user_id=u) for u in batch_ids],
                    ignore_conflicts=True,
                )

        # Async side effects (use your Celery tasks)
        # 1) Push in one go by ids (your task already takes list of ids)
        try:
            send_push_notification.delay(ids, subject, message)
        except Exception:
            pass  # don't break the response on side-effect failures

        # 2) Fan out emails as individual tasks (or implement a batched task)
        for e in emails:
            try:
                send_notification_email.delay(e, subject, message)
            except Exception:
                continue

        return Response(
            {
                "message": f"Notification sent to {len(ids)} user(s).",
                "notification_id": notif.id,
                "counts": {"employees": emp_count, "trainees": trn_count},
                "audience": audience,
                "mode": mode,
                "department_scope": dept_arg or trainer_dept or None,
            },
            status=200,
        )

class AdminTrainingReportView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # ---- helper to build a detailed report for trainee/employee ----
    def _build_detailed_report(self, target_user):
        profile = None
        completions = []

        if target_user.role == 'trainee':
            profile = (TraineeProfile.objects
                    .select_related('trainer', 'user')
                    .filter(user=target_user).first())
            if profile:
                completions = (TraineeLessonCompletion.objects
                            .filter(trainee=profile)
                            .select_related('lesson'))
        elif target_user.role == 'employee':
            profile = (EmployeeProfile.objects
                    .select_related('user')
                    .filter(user=target_user).first())
            if profile:
                completions = (EmployeeLessonCompletion.objects
                            .filter(employee=profile)
                            .select_related('lesson'))

        name = getattr(profile, 'name', 'N/A') if profile else 'N/A'
        trainer_name = getattr(getattr(profile, 'trainer', None), 'name', 'N/A')

        return {
            'user_id': target_user.id,
            'username': target_user.username,
            'role': target_user.role,
            'name': name,
            'employee_id': getattr(profile, 'employee_id', 'N/A') if profile else 'N/A',
            'department': getattr(profile, 'department', 'N/A') if profile else 'N/A',
            'designation': getattr(profile, 'designation', 'N/A') if profile else 'N/A',
            'trainer_name': trainer_name,
            # CRUCIAL: pass model instances, not dicts
            'completed_lessons': list(completions),
        }


    def list(self, request):
        """List reports visible to the requester.
        - admin: all trainees + employees
        - trainer: assigned trainees + their own employee user (if any)
        """
        user = request.user

        if user.role == 'admin':
            users = CustomUser.objects.filter(
                Q(role='trainee') | Q(role='employee'),
                is_active=True
            ).distinct()

        elif user.role == 'trainer':
            try:
                trainee_user_ids = (
                    TraineeProfile.objects
                    .filter(trainer_id=user.id)
                    .values_list('user_id', flat=True)
                )
                users = CustomUser.objects.filter(
                    Q(id__in=trainee_user_ids) | Q(id=user.id, role='employee'),
                    is_active=True
                ).distinct()
            except Exception as e:
                return Response(
                    {"error": f"Error fetching trainees: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)

        report_data = []
        for u in users:
            # detailed only for trainee/employee; (trainers won't appear in list anyway)
            if u.role in ('trainee', 'employee'):
                report_data.append(self._build_detailed_report(u))
            else:
                report_data.append({
                    'user_id': u.id,
                    'username': u.username,
                    'role': u.role,
                    'name': getattr(u, 'get_full_name', lambda: None)() or u.username,
                    'employee_id': 'N/A',
                    'department': 'N/A',
                    'designation': 'N/A',
                    'trainer_name': 'N/A',
                    'completed_lessons': [],
                })

        serializer = TrainingReportSerializer(report_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        """Detailed report for a specific user (trainee/employee)."""
        requester = request.user
        try:
            target_user = CustomUser.objects.get(id=pk)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # ---- authorization ----
        if requester.role == 'admin':
            pass  # Admin can view anyone
        elif requester.role == 'trainer':
            if target_user.role == 'trainee':
                # Only if this trainee is assigned to this trainer
                if not TraineeProfile.objects.filter(user=target_user, trainer_id=requester.id).exists():
                    return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
            elif target_user.role == 'employee':
                # Trainers can view only their own employee account (keep as-is; relax if desired)
                if target_user.id != requester.id:
                    return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)

        # ---- build detailed report (works for trainee & employee) ----
        data = self._build_detailed_report(target_user)
        serializer = TrainingReportSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class SmallPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200

BULK_CHUNK = 2000  # tune to your DB

class AdminNotifyView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        # Same auth gate as POST
        role = getattr(request.user, "role", None)
        if role != "admin" and not request.user.is_staff:
            return Response({"error": "Only admin can view their sent notifications."},
                            status=status.HTTP_403_FORBIDDEN)

        qs = (
            Notification.objects.filter(sent_by=request.user)
            .annotate(recipients_count=Count("notificationreceipt", distinct=True))
        )

        # --- Filters ---
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(subject__icontains=search)
                | Q(message__icontains=search)
                | Q(link__icontains=search)
            )

        date_from = (request.query_params.get("date_from") or "").strip()
        date_to = (request.query_params.get("date_to") or "").strip()
        # filter only if your Notification has created_at (adjust if different)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        qs = qs.order_by("-created_at", "-id")  # safe even if created_at ties

        paginator = SmallPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        ser = SentNotificationSerializer(page, many=True)
        return paginator.get_paginated_response(ser.data)


    @swagger_auto_schema(
        operation_description="""
        Send notifications (Trainer → Employees/Trainees).

        Modes:
        - individual: pass `usernames` (list of usernames; employees and/or trainees)
        - group:
            audience: employee | trainee | both
            department (optional, employees only; defaults to trainer's department if available)
        """,
        request_body=TrainerNotificationRequestSerializer,
        responses={200: openapi.Response("OK"), 400: "Bad Request", 403: "Forbidden", 404: "Not Found"}
    )
    def post(self, request):
        role = getattr(request.user, "role", None)
        if role != "admin" and not request.user.is_staff:
            return Response({"error": "Only admin can send notifications."}, status=status.HTTP_403_FORBIDDEN)

        ser = TrainerNotificationRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        subject    = data["subject"].strip()
        message    = data["message"].strip()
        link       = (data.get("link") or "").strip() or None
        notif_type = data["notification_type"]
        mode       = data["mode"]
        audience   = data["audience"]          # employee | trainee | both
        dept_arg   = (data.get("department") or "").strip() or None

        # Get trainer dept (fallback)
        trainer_dept = None
        try:
            tp = AdminProfile.objects.only("department").get(user=request.user)
            trainer_dept = tp.department
        except AdminProfile.DoesNotExist:
            pass

        # ---------- Build recipients ----------
        base_q = Q(is_active=True)
        role_q = Q()

        if mode == "individual":
            usernames = data.get("usernames") or []
            if not usernames:
                return Response({"error": "`usernames` is required for individual mode."}, status=400)

            # normalize + dedupe
            usernames = list({str(u).strip() for u in usernames if str(u).strip()})
            if not usernames:
                return Response({"error": "No valid usernames provided."}, status=400)

            # Optionally enforce audience subset:
            # if audience != "both":
            #     role_q = Q(role=("employee" if audience == "employee" else "trainee"))

            qs = CustomUser.objects.filter(base_q, Q(username__in=usernames)).only("id", "email", "role")
        elif mode == "group":
            if audience in ("employee", "both"):
                if dept_arg:
                    role_q |= Q(role="employee", employee_profile__department=dept_arg)
                elif trainer_dept:
                    role_q |= Q(role="employee", employee_profile__department=trainer_dept)
                else:
                    role_q |= Q(role="employee")

            if audience in ("trainee", "both"):
                role_q |= Q(role="trainee")

            if role_q.children == []:
                return Response({"error": "Invalid audience for group mode."}, status=400)

            qs = CustomUser.objects.filter(base_q & role_q).only("id", "email", "role")
        else:
            return Response({"error": "Invalid mode. Use 'individual' or 'group'."}, status=400)

        # Exclude sender & dedupe
        qs = qs.exclude(id=request.user.id).distinct()

        # Pull ids/emails without materializing full objects
        recipients = list(qs.values_list("id", "email", "role"))
        if not recipients:
            return Response({"error": "No matching recipients found."}, status=404)

        ids    = [r[0] for r in recipients]
        emails = [r[1] for r in recipients if r[1]]
        roles  = [r[2] for r in recipients]

        emp_count = sum(1 for r in roles if r == "employee")
        trn_count = sum(1 for r in roles if r == "trainee")

        # ---------- Write + side-effects ----------
        with transaction.atomic():
            notif = Notification.objects.create(
                subject=subject,
                message=message,
                link=link,
                notification_type=notif_type,
                sent_by=request.user,
            )

            # Bulk receipts in chunks (better on large sends)
            from itertools import islice
            def chunks(seq, n):
                it = iter(seq)
                while True:
                    batch = list(islice(it, n))
                    if not batch:
                        break
                    yield batch

            for batch_ids in chunks(ids, BULK_CHUNK):
                NotificationReceipt.objects.bulk_create(
                    [NotificationReceipt(notification=notif, user_id=u) for u in batch_ids],
                    ignore_conflicts=True,
                )

        # Async side effects (use your Celery tasks)
        # 1) Push in one go by ids (your task already takes list of ids)
        try:
            send_push_notification.delay(ids, subject, message)
        except Exception:
            pass  # don't break the response on side-effect failures

        # 2) Fan out emails as individual tasks (or implement a batched task)
        for e in emails:
            try:
                send_notification_email.delay(e, subject, message)
            except Exception:
                continue

        return Response(
            {
                "message": f"Notification sent to {len(ids)} user(s).",
                "notification_id": notif.id,
                "counts": {"employees": emp_count, "trainees": trn_count},
                "audience": audience,
                "mode": mode,
                "department_scope": dept_arg or trainer_dept or None,
            },
            status=200,
        )
    
class AdminSOPListView(BaseSOPListView):
    REQUIRED_ROLE = "admin"

class AdminLibraryListView(BaseSLListView):
    required_role = "admin"

class AdminTrainerLessonProgressListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminTrainerLessonProgressSerializer
    pagination_class = None

    def get_queryset(self):
        qs = (
            TrainerLessonProgress.objects
            .select_related("trainer", "trainer__user", "lesson", "lesson__course")
            .all()
            .order_by("-last_accessed_at")
        )

        trainer_id = self.request.query_params.get("trainer_id")
        department = self.request.query_params.get("department")
        course_id  = self.request.query_params.get("course_id")
        status     = self.request.query_params.get("status")
        min_date   = self.request.query_params.get("min_date")
        max_date   = self.request.query_params.get("max_date")
        search     = self.request.query_params.get("search")

        if trainer_id:
            qs = qs.filter(trainer_id=trainer_id)
        if department:
            qs = qs.filter(trainer__department__iexact=department)
        if course_id:
            qs = qs.filter(lesson__course_id=course_id)
        if status in {"not_started", "in_progress", "completed"}:
            qs = qs.filter(status=status)

        def parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except Exception:
                return None

        if min_date:
            dt = parse_date(min_date)
            if dt:
                qs = qs.filter(last_accessed_at__date__gte=dt.date())
        if max_date:
            dt = parse_date(max_date)
            if dt:
                qs = qs.filter(last_accessed_at__date__lte=dt.date())

        if search:
            qs = qs.filter(
                Q(trainer__user__username__icontains=search) |
                Q(trainer__user__first_name__icontains=search) |
                Q(trainer__user__last_name__icontains=search) |
                Q(lesson__lesson_name__icontains=search) |         # ← FIXED
                Q(lesson__course__course_name__icontains=search)    # ← FIXED
            )

        return qs

class AdminTrainerCourseProgressView(ListAPIView):
    """
    Admin: per-course progress for ALL trainers (no trainer_id needed).
    Optional filters:
      - ?trainer_id=<int>
      - ?department=<str>
      - ?only_approved=true
      - ?frontend_only=true
    """
    permission_classes = [IsAuthenticated]            # ✅ require auth
    serializer_class = AdminCourseProgressRowSerializer
    pagination_class = None

    def get_queryset(self):
        # ✅ avoid schema gen crash when drf_yasg calls without a user
        if getattr(self, "swagger_fake_view", False):
            return Courses.objects.none()
        return []

    def list(self, request, *args, **kwargs):
        user = request.user

        # ✅ explicit auth/role checks (return 401/403 instead of 500)
        if not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        if getattr(user, "role", "").lower() != "admin":
            return Response({"detail": "Admin only."}, status=403)

        qp = request.query_params
        trainer_id = qp.get("trainer_id")
        dept_filter = qp.get("department")
        only_approved = qp.get("only_approved", "false").lower() in ("1", "true", "yes")
        frontend_only = qp.get("frontend_only", "true").lower() in ("1", "true", "yes")

        trainers_qs = TrainerProfile.objects.select_related("user")
        if trainer_id:
            trainers_qs = trainers_qs.filter(id=trainer_id)
        if dept_filter:
            trainers_qs = trainers_qs.filter(department=dept_filter)

        trainers = list(trainers_qs)
        if not trainers:
            return Response([])

        departments = {t.department for t in trainers if getattr(t, "department", None)}
        if not departments:
            return Response([])

        course_filters = Q(department__in=list(departments))
        if frontend_only:
            course_filters &= Q(display_on_frontend=True)
        if only_approved:
            course_filters &= Q(is_approved=True)

        courses_qs = Courses.objects.filter(course_filters).only(
            "id", "course_id", "course_name", "department", "display_on_frontend", "is_approved"
        )

        courses_by_dept = {}
        for c in courses_qs:
            courses_by_dept.setdefault(c.department, []).append(c)

        lesson_filters = Q(course__in=courses_qs)
        if frontend_only:
            lesson_filters &= Q(display_on_frontend=True)
        if only_approved:
            lesson_filters &= Q(is_approved=True)

        total_by_course_pk = dict(
            CourseLesson.objects
            .filter(lesson_filters)
            .values("course_id")
            .annotate(total=Count("id"))
            .values_list("course_id", "total")
        )

        progress_filters = Q(
            lesson__course__in=courses_qs,
            trainer__in=trainers_qs,
            status="completed",
        )
        if frontend_only:
            progress_filters &= Q(lesson__display_on_frontend=True)
        if only_approved:
            progress_filters &= Q(lesson__is_approved=True)

        completed_by_tc = dict(
            TrainerLessonProgress.objects
            .filter(progress_filters)
            .values("trainer_id", "lesson__course_id")
            .annotate(done=Count("id"))
            .values_list("trainer_id", "lesson__course_id", "done")
        )

        def trainer_name(t):
            u = getattr(t, "user", None)
            if u and hasattr(u, "get_full_name"):
                n = u.get_full_name() or ""
                if n.strip():
                    return n.strip()
            return getattr(u, "username", f"trainer-{t.id}")

        payload = []
        for t in trainers:
            dept = getattr(t, "department", None)
            for c in courses_by_dept.get(dept, []):
                total = int(total_by_course_pk.get(c.id, 0) or 0)
                done = int(completed_by_tc.get((t.id, c.id), 0) or 0)
                percent = int(round((done / total) * 100)) if total else 0
                payload.append({
                    "trainer_id": t.id,
                    "trainer_username": getattr(getattr(t, "user", None), "username", ""),
                    "trainer_name": trainer_name(t),
                    "trainer_department": dept or "",
                    "course_pk": c.id,
                    "course_id": c.course_id,
                    "course_name": c.course_name,
                    "total_lessons": total,
                    "completed_lessons": done,
                    "completion_percent": percent,
                })

        payload.sort(key=lambda x: (-x["completion_percent"], x["trainer_name"].lower(), x["course_name"].lower()))
        return Response(payload)

class AdminTrainerOverallSummaryView(ListAPIView):
    """
    Overall completion for each trainer (optionally filter by department).
    Returns one row per trainer with totals across all visible courses in their department.

    Query params:
      - department (str, optional)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AdminTrainerSummaryRowSerializer
    pagination_class = None

    def get_queryset(self):
        return []

    def list(self, request, *args, **kwargs):
        department = request.query_params.get("department")

        trainers = TrainerProfile.objects.select_related("user")
        if department:
            trainers = trainers.filter(department__iexact=department)

        # Gather all courses per department
        # To avoid N+1, we’ll compute per-trainer using two passes of dicts.

        # Total lessons by department-course
        lessons_by_course = (
            CourseLesson.objects
            .filter(course__display_on_frontend=True, display_on_frontend=True)
            .values("course_id", "course__department")
            .annotate(total=Count("id"))
        )

        # Map dept -> {course_id: total}
        totals_by_dept = {}
        for row in lessons_by_course:
            dept = row["course__department"]
            course_id = row["course_id"]
            totals_by_dept.setdefault(dept, {})[course_id] = row["total"]

        # Completed by trainer-course
        completed_qs = (
            TrainerLessonProgress.objects
            .filter(
                lesson__display_on_frontend=True,
                lesson__course__display_on_frontend=True,
                status="completed",
            )
            .values("trainer_id", "lesson__course_id")
            .annotate(done=Count("id"))
        )

        # Map (trainer_id) -> {course_id: done}
        completed_by_trainer = {}
        for row in completed_qs:
            tid = row["trainer_id"]
            cid = row["lesson__course_id"]
            completed_by_trainer.setdefault(tid, {})[cid] = row["done"]

        payload = []
        for t in trainers:
            dept_totals = totals_by_dept.get(t.department, {})  # totals for courses in this dept
            if not dept_totals:
                total_lessons = 0
            else:
                # Only count courses that exist in this department
                total_lessons = sum(dept_totals.values())

            trainer_completed_map = completed_by_trainer.get(t.id, {})
            completed_lessons = 0
            if dept_totals:
                # Only count completed for courses in this department
                for cid, total in dept_totals.items():
                    completed_lessons += int(trainer_completed_map.get(cid, 0))

            percent = int(round((completed_lessons / total_lessons) * 100)) if total_lessons else 0

            u = t.user
            full = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
            payload.append({
                "trainer_id": t.id,
                "trainer_username": u.username,
                "trainer_name": full or u.username,
                "department": t.department or "",
                "total_lessons": int(total_lessons),
                "completed_lessons": int(completed_lessons),
                "completion_percent": percent,
            })

        # Sort by completion desc, then name
        payload.sort(key=lambda x: (-x["completion_percent"], x["trainer_name"].lower()))
        return Response(payload)
    
class TraineeFeedbackAdminListView(generics.ListAPIView):
    """
    Admin dashboard list with filters:
    ?username=<str>
    &date_from=YYYY-MM-DD or ISO
    &date_to=YYYY-MM-DD or ISO
    &min_comm=1&max_comm=5
    &min_subj=1&max_subj=5
    &min_ment=1&max_ment=5
    &search=<text in custom_feedback or username>
    """
    serializer_class = TraineeFeedbackSerializer
    pagination_class = None  # add your PageNumberPagination if you want paging

    def get_queryset(self):
        qs = TraineeFeedback.objects.select_related('trainee').all().order_by('-created_at')
        p = self.request.query_params

        username = p.get('username')
        if username:
            qs = qs.filter(trainee__username__iexact=username)

        date_from = p.get('date_from')
        if date_from:
            dt = parse_datetime(date_from) or parse_datetime(f"{date_from}T00:00:00")
            if dt:
                qs = qs.filter(created_at__gte=dt)

        date_to = p.get('date_to')
        if date_to:
            dt = parse_datetime(date_to) or parse_datetime(f"{date_to}T23:59:59")
            if dt:
                qs = qs.filter(created_at__lte=dt)

        def _int(qp, key, default=None):
            try:
                return int(qp.get(key))
            except (TypeError, ValueError):
                return default

        min_comm = _int(p, 'min_comm')
        max_comm = _int(p, 'max_comm')
        if min_comm is not None: qs = qs.filter(communication__gte=min_comm)
        if max_comm is not None: qs = qs.filter(communication__lte=max_comm)

        min_subj = _int(p, 'min_subj')
        max_subj = _int(p, 'max_subj')
        if min_subj is not None: qs = qs.filter(subject_knowledge__gte=min_subj)
        if max_subj is not None: qs = qs.filter(subject_knowledge__lte=max_subj)

        min_ment = _int(p, 'min_ment')
        max_ment = _int(p, 'max_ment')
        if min_ment is not None: qs = qs.filter(mentorship__gte=min_ment)
        if max_ment is not None: qs = qs.filter(mentorship__lte=max_ment)

        search = p.get('search')
        if search:
            qs = qs.filter(
                Q(custom_feedback__icontains=search) |
                Q(trainee__username__icontains=search)
            )

        return qs

BULK_CHUNK = 1000
ROLE_TRAINER  = "trainer"
ROLE_EMPLOYEE = "employee"
ROLE_TRAINEE  = "trainee"
ROLE_ADMIN    = "admin"

class AdminNotifyView(APIView):
    """
    Admin/staff notifications endpoint:
      - GET: list inbox/sent/both for the authenticated admin/staff
      - POST: send to trainer/employee/trainee (any combination), with optional dept scoping
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    # --------------------- PERM CHECK ---------------------
    def _ensure_admin(self, request):
        if not (getattr(request.user, "is_staff", False) or getattr(request.user, "role", None) == ROLE_ADMIN):
            return False
        return True

    # ----------------------- GET -------------------------
    def get(self, request):
        """
        List notifications.

        Query params:
        - box: sent | inbox | both  (default: sent)
        - search: str (subject/message/link contains)
        - date_from: YYYY-MM-DD (created_at >=)
        - date_to: YYYY-MM-DD (created_at <=)
        - from_admin: true|false (only show those sent_by staff/admin)
        """
        if not self._ensure_admin(request):
            return Response({"error": "Only admin/staff can access this endpoint."}, status=status.HTTP_403_FORBIDDEN)

        box = (request.query_params.get("box") or "sent").strip().lower()
        if box not in ("sent", "inbox", "both"):
            box = "sent"

        search = (request.query_params.get("search") or "").strip()
        date_from = (request.query_params.get("date_from") or "").strip()
        date_to = (request.query_params.get("date_to") or "").strip()
        from_admin = (request.query_params.get("from_admin") or "").strip().lower() in ("1", "true", "yes")

        paginator = SmallPageNumberPagination()

        def apply_common_filters(qs):
            if search:
                qs = qs.filter(
                    Q(subject__icontains=search)
                    | Q(message__icontains=search)
                    | Q(link__icontains=search)
                )
            if date_from:
                qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(created_at__date__lte=date_to)
            if from_admin:
                qs = qs.filter(Q(sent_by__is_staff=True) | Q(sent_by__role=ROLE_ADMIN))
            return qs.order_by("-created_at", "-id")

        payload = {}

        if box in ("sent", "both"):
            sent_qs = (
                Notification.objects
                .filter(sent_by=request.user)
                .annotate(recipients_count=Count("notificationreceipt", distinct=True))
            )
            sent_qs = apply_common_filters(sent_qs)
            sent_page = paginator.paginate_queryset(sent_qs, request) if box == "sent" else list(sent_qs[:50])
            payload["sent"] = SentNotificationSerializer(sent_page, many=True).data

        if box in ("inbox", "both"):
            # Inbox for admin will list any notifications with a receipt addressed to them
            receipt_sq = NotificationReceipt.objects.filter(
                notification_id=OuterRef("pk"),
                user_id=request.user.id,
            ).values("read_at")[:1]

            exists_receipt = NotificationReceipt.objects.filter(
                notification_id=OuterRef("pk"),
                user_id=request.user.id,
            )

            inbox_qs = (
                Notification.objects
                .annotate(
                    _has_my_receipt=Exists(exists_receipt),
                    my_read_at=Subquery(receipt_sq, output_field=DateTimeField()),
                )
                .filter(_has_my_receipt=True)
            )
            inbox_qs = apply_common_filters(inbox_qs)
            inbox_page = paginator.paginate_queryset(inbox_qs, request) if box == "inbox" else list(inbox_qs[:50])
            payload["inbox"] = InboxNotificationSerializer(inbox_page, many=True).data

        if box == "both":
            return Response(payload, status=200)
        return paginator.get_paginated_response(payload.get(box, []))

    # ----------------------- POST ------------------------
    @swagger_auto_schema(
        operation_description="""
        Admin/staff: Send notifications to any combination of roles with optional department scoping.

        Modes:
        - individual: provide `usernames` (list)
        - group: provide `audience_roles` (preferred) or legacy `audience` (employee|trainee|trainer|both|all)
                 Optional `departments` applies to employees and trainers.
        """,
        request_body=AdminNotificationRequestSerializer,
        responses={200: openapi.Response("OK"), 400: "Bad Request", 403: "Forbidden", 404: "Not Found"}
    )
    def post(self, request):
        if not self._ensure_admin(request):
            return Response({"error": "Only admin/staff can send notifications."}, status=status.HTTP_403_FORBIDDEN)

        ser = AdminNotificationRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        subject    = data["subject"].strip()
        message    = data["message"].strip()
        link       = (data.get("link") or "").strip() or None
        notif_type = data["notification_type"]
        mode       = data["mode"]
        depts      = data.get("departments") or None   # list[str] or None

        base_q = Q(is_active=True)

        # ---------- Build recipients ----------
        if mode == "individual":
            usernames = data.get("usernames") or []
            qs = CustomUser.objects.filter(base_q, username__in=usernames).only("id", "email", "role")

        elif mode == "group":
            roles = data.get("audience") or []  # always a list per serializer
            role_q = Q()

            if ROLE_EMPLOYEE in roles:
                emp_q = Q(role=ROLE_EMPLOYEE)
                if depts:
                    emp_q &= Q(employee_profile__department__in=depts)
                role_q |= emp_q

            if ROLE_TRAINER in roles:
                trn_q = Q(role=ROLE_TRAINER)
                # Scope trainers by dept only if you actually store it; otherwise drop this block
                if depts:
                    trn_q &= Q(trainer_profile__department__in=depts)
                role_q |= trn_q

            if ROLE_TRAINEE in roles:
                role_q |= Q(role=ROLE_TRAINEE)

            if not role_q.children:
                return Response({"error": "No valid roles requested."}, status=400)

            qs = CustomUser.objects.filter(base_q & role_q).only("id", "email", "role")

        else:
            return Response({"error": "Invalid mode. Use 'individual' or 'group'."}, status=400)

        qs = qs.exclude(id=request.user.id).distinct()
        recipients = list(qs.values_list("id", "email", "role"))
        if not recipients:
            return Response({"error": "No matching recipients found."}, status=404)

        ids    = [r[0] for r in recipients]
        emails = [r[1] for r in recipients if r[1]]
        roles  = [r[2] for r in recipients]

        emp_count = sum(1 for r in roles if r == ROLE_EMPLOYEE)
        trn_count = sum(1 for r in roles if r == ROLE_TRAINEE)
        tnr_count = sum(1 for r in roles if r == ROLE_TRAINER)

        # ---------- Create notification + receipts ----------
        from itertools import islice
        def chunks(seq, n):
            it = iter(seq)
            while True:
                batch = list(islice(it, n))
                if not batch:
                    break
                yield batch

        with transaction.atomic():
            notif = Notification.objects.create(
                subject=subject,
                message=message,
                link=link,
                notification_type=notif_type,
                sent_by=request.user,
            )

            for batch in chunks(ids, BULK_CHUNK):
                NotificationReceipt.objects.bulk_create(
                    [NotificationReceipt(notification=notif, user_id=u) for u in batch],
                    ignore_conflicts=True,
                )

        # ---------- Optional async fanout ----------
        # try:
        #     send_push_notification.delay(ids, subject, message)
        # except Exception:
        #     pass
        # for e in emails:
        #     try:
        #         send_notification_email.delay(e, subject, message)
        #     except Exception:
        #         continue

        return Response(
            {
                "message": f"Notification sent to {len(ids)} user(s).",
                "notification_id": notif.id,
                "counts": {"employees": emp_count, "trainees": trn_count, "trainers": tnr_count},
                "audience": sorted(list(set(roles))),
                "mode": mode,
                "departments": depts,
            },
            status=200,
        )


class AdminLessonListCreateView(ListCreateAPIView):
    """Admin view to list and create lessons with multiple PDFs"""
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        return Lesson.objects.all().select_related('subject').order_by('position')
    
    def perform_create(self, serializer):
        serializer.save()


class AdminLessonDetailView(RetrieveUpdateAPIView):
    """Admin view to retrieve, update, or delete a lesson"""
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Lesson.objects.all().select_related('subject')


class AdminLessonUploadPDFView(APIView):
    """Admin view to upload multiple PDFs to a lesson"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, lesson_id):
        try:
            lesson = get_object_or_404(Lesson, id=lesson_id)
            pdf_files = request.FILES.getlist('pdf_files')
            
            if not pdf_files:
                return Response({"error": "No PDF files provided"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate PDF files
            from django.core.files.base import ContentFile
            from django.core.validators import FileExtensionValidator
            from django.core.exceptions import ValidationError
            
            pdf_paths = lesson.lesson_pdfs or []
            
            for pdf_file in pdf_files:
                # Validate file extension
                if not pdf_file.name.lower().endswith('.pdf'):
                    return Response({"error": f"File {pdf_file.name} is not a PDF"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate file size (10MB max)
                if pdf_file.size > 10 * 1024 * 1024:
                    return Response({"error": f"File {pdf_file.name} is too large (max 10MB)"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Save file and get path
                from django.core.files.storage import default_storage
                from django.utils import timezone
                import os
                
                filename = f"lesson_pdfs/{timezone.now().strftime('%Y/%m')}/{lesson.lesson_id}_{pdf_file.name}"
                path = default_storage.save(filename, pdf_file)
                pdf_paths.append(path)
            
            # Update lesson with new PDF paths
            lesson.lesson_pdfs = pdf_paths
            lesson.save()
            
            return Response({
                "message": f"Successfully uploaded {len(pdf_files)} PDF files",
                "pdf_paths": pdf_paths
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, lesson_id):
        try:
            lesson = get_object_or_404(Lesson, id=lesson_id)
            pdf_path = request.data.get('pdf_path')
            
            if not pdf_path:
                return Response({"error": "PDF path is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if pdf_path not in (lesson.lesson_pdfs or []):
                return Response({"error": "PDF not found in this lesson"}, status=status.HTTP_404_NOT_FOUND)
            
            # Remove file from storage
            from django.core.files.storage import default_storage
            try:
                default_storage.delete(pdf_path)
            except Exception:
                pass  # File might not exist
            
            # Remove path from lesson
            pdf_paths = lesson.lesson_pdfs or []
            pdf_paths.remove(pdf_path)
            lesson.lesson_pdfs = pdf_paths
            lesson.save()
            
            return Response({
                "message": "PDF successfully removed",
                "remaining_pdfs": pdf_paths
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)