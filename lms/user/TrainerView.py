from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.db.models.functions import TruncDate
from user.models import (
    TrainerProfile,TraineeProfile, CustomUser,Courses,CourseLesson,Microplanner,Macroplanner,Assessment,AssessmentReport,EvaluationRemark,TrainingReport,UserLoginActivity,QueryResponse,
    Query,EmployeeProfile,Notification,NotificationReceipt,TraineeLessonCompletion,EmployeeLessonCompletion,TrainerLessonProgress,TraineeTaskSubmission,
    TaskAssignment
)
from user.serializers import (
    TrainerSerializer,CourseSerializer, CourseLessonSerializer, MacroplannerSerializer, MicroplannerSerializer,AssessmentSerializer,AssessmentReportSerializer,
    EvaluationRemarkSerializer,TrainingReportSerializer,UserLoginActivitySerializer,QueryResponseSerializer,QuerySerializer,
    EmployeeSerializer,TrainerNotificationRequestSerializer,SentNotificationSerializer,ActiveUserSerializer,TrainerLessonProgressWriteSerializer,
    InboxNotificationSerializer,TrainerLessonProgressReadSerializer,TaskAssignmentCreateSerializer,TaskAssignmentSerializer,LinkSubmissionSerializer,
    TraineeSerializer
)
from rest_framework.generics import ListCreateAPIView,RetrieveUpdateAPIView, ListAPIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework import status,permissions
from .tasks import send_notification_email, send_push_notification
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from .utils import get_active_users
from django.db import transaction
from datetime import date
from django.db.models import Q, Count,Case, When, Value, CharField, F
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import FieldDoesNotExist
from quiz.models import Quiz
from .utils import get_active_users,get_trainer_profile
from .views import BaseSLListView,BaseSOPListView
from django.db.models import Q, Count, OuterRef, Subquery, DateTimeField, Exists
from django.utils import timezone

class TrainerDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            trainer_obj = TrainerProfile.objects.get(user=request.user)
            department = trainer_obj.department
        except TrainerProfile.DoesNotExist:
            return Response({"error": "Trainer profile not found."}, status=404)

        # Profile data
        profile_data = TrainerSerializer(trainer_obj, context={'request': request}).data
        DEPARTMENT_ACCESS_MAP = {
            "Development": "Training",
            "Shop Editing": "Shop Editor Training",
        }


        # Get mapped trainee department
        allowed_trainee_department = DEPARTMENT_ACCESS_MAP.get(department)

        if not allowed_trainee_department:
            return Response({"error": "No department access configured"}, status=403)

        # Filter trainees dynamically
        all_trainees = (
            TraineeProfile.objects
            .filter(department=allowed_trainee_department)
            .select_related('user', 'trainer')
        )
        
        # Count of all trainees with department "Training"
        total_trainees = all_trainees.count()
        
        # Count of trainees assigned to this trainer
        assigned_trainees_count = all_trainees.filter(trainer=request.user).count()

        # Serialize all trainees
        trainees_data = TraineeSerializer(all_trainees, many=True, context={'request': request}).data

        # Courses (we can later add filtering by department or trainer-assigned logic)
        courses = Courses.objects.filter(department=department)
        course_count = courses.count()

        # Active users in the trainer's department
        active_users = get_active_users(department).select_related("trainee_profile", "employee_profile")
        data = ActiveUserSerializer(active_users, many=True).data
        active_count = active_users.count()

        return Response({
            "profile": profile_data,
            "trainee_count": total_trainees,
            "assigned_trainee_count": assigned_trainees_count,
            "trainees": trainees_data,
            "course_count": course_count,
            "courses": list(courses.values("course_id", "course_name", "department", "is_approved")),
            "active_count": active_count,
            "active_users": data,
        }, status=200)


class TraineeListAPIView(APIView):
    """
    GET /trainer/trainees/
    Returns trainees whose department matches the trainer's department.
    Available for trainers to view their department's trainees.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of trainees from the same department as the trainer.",
        responses={
            200: "List of trainees",
            403: "Forbidden - Only trainers can access this endpoint",
            404: "Trainer profile not found"
        },
    )
    def get(self, request):
        # Check if user is a trainer
        if request.user.role != 'trainer':
            return Response(
                {"error": "Only trainers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get trainer's department
        try:
            trainer_profile = TrainerProfile.objects.get(user=request.user)
            trainer_department = trainer_profile.department
        except TrainerProfile.DoesNotExist:
            return Response(
                {"error": "Trainer profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Map trainer department to trainee department
        # Trainers with "Development" department see trainees with "Training" department
        # All other trainers see trainees from their same department
        if trainer_department == "Development":
            trainee_department = "Training"
        elif trainer_department == "Shop Editing":
            trainee_department = "Shop Editor Training"
        else:
            trainee_department = trainer_department

        # Get all trainees with the mapped department
        trainees = TraineeProfile.objects.filter(
            department=trainee_department
        ).select_related('user', 'trainer').order_by('user__username')

        # Serialize trainees
        serializer = TraineeSerializer(trainees, many=True, context={'request': request})
        
        return Response({
            "trainees": serializer.data,
            "trainer_department": trainer_department,
            "count": trainees.count()
        }, status=status.HTTP_200_OK)


class TrainerCourseView(ListCreateAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def get_queryset(self):
        try:
            trainer = TrainerProfile.objects.get(user=self.request.user)
            return Courses.objects.filter(department=trainer.department, display_on_frontend=True)
        except TrainerProfile.DoesNotExist:
            return Courses.objects.none()


    def perform_create(self, serializer):
        trainer = get_object_or_404(TrainerProfile, user=self.request.user)
        serializer.save(created_by=self.request.user, department=trainer.department)



class TrainerCourseLessonView(ListCreateAPIView):
    serializer_class = CourseLessonSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def get_queryset(self):
        trainer = get_object_or_404(TrainerProfile, user=self.request.user)
        return CourseLesson.objects.filter(
            course__department=trainer.department,
            display_on_frontend=True
        )

    def perform_create(self, serializer):
        trainer = get_object_or_404(TrainerProfile, user=self.request.user)
        serializer.save(created_by=self.request.user)


class MacroplannerViewSet(viewsets.ModelViewSet):
    serializer_class = MacroplannerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            trainer = TrainerProfile.objects.get(user=self.request.user)
            return Macroplanner.objects.filter(department=trainer.department)
        except TrainerProfile.DoesNotExist:
            raise PermissionDenied("Only trainers can access department-specific planners.")

    def perform_create(self, serializer):
        trainer = TrainerProfile.objects.get(user=self.request.user)
        serializer.save(department=trainer.department)

    def perform_update(self, serializer):
        trainer = TrainerProfile.objects.get(user=self.request.user)
        serializer.save(department=trainer.department)


class MicroplannerViewSet(viewsets.ModelViewSet):
    serializer_class = MicroplannerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            trainer = TrainerProfile.objects.get(user=self.request.user)
            return Microplanner.objects.filter(department=trainer.department)
        except TrainerProfile.DoesNotExist:
            raise PermissionDenied("Only trainers can access department-specific planners.")

    def perform_create(self, serializer):
        trainer = TrainerProfile.objects.get(user=self.request.user)
        serializer.save(department=trainer.department)

    def perform_update(self, serializer):
        trainer = TrainerProfile.objects.get(user=self.request.user)
        serializer.save(department=trainer.department)


class AssessmentListCreateView(ListCreateAPIView):
    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Assessment.objects.filter(assigned_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)


class TrainerAssessmentReportView(APIView):
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
    
class LMSEngagementView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserLoginActivitySerializer

    def get_trainer_department(self):
        try:
            tp = TrainerProfile.objects.get(user=self.request.user)
        except TrainerProfile.DoesNotExist:
            raise NotFound("Trainer profile not found.")
        # works whether department is a string or FK object
        return tp.department

    def get_queryset(self):
        dept = self.get_trainer_department()

        # Collect usernames for BOTH trainees and employees in this department
        trainee_usernames = TraineeProfile.objects.filter(
            department=dept
        ).values_list("user__username", flat=True)

        employee_usernames = EmployeeProfile.objects.filter(
            department=dept
        ).values_list("user__username", flat=True)

        usernames = list(set(list(trainee_usernames) + list(employee_usernames)))
        if not usernames:
            return UserLoginActivity.objects.none()

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
                # ignore bad month format or raise a ValidationError if you prefer
                pass

        return qs
        
# class TrainerDashboardViewSet(viewsets.ViewSet):
#     permission_classes = [IsAuthenticated]

#     @action(detail=False, methods=['get'], url_path='active-users')
#     def active_users(self, request):
#         """Return the list of active (logged-in) students for the teacher's school."""
#         user = request.user
#         try:
#             teacher_obj = TrainerProfile.objects.get(user=user)
#             department= teacher_obj.department
#         except TrainerProfile.DoesNotExist:
#             raise NotFound(detail="Teacher record not found for this user.")

#         # ✅ Get active students from the same school
#         active_students = get_active_students(department)
#         serialized_students = EmployeeSerializer(active_students, many=True).data

#         return Response({"active_users": serialized_students})
    

class RecentActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            trainer_obj = TrainerProfile.objects.get(user=request.user)
            department_instance = trainer_obj.department
        except TrainerProfile.DoesNotExist:
            raise NotFound(detail="Mentor record not found for this user.")
        
        # Cache key
        cache_key = f"recent_activity_{trainer_obj.pk}"

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

        response_data=({
            "recent_activity": {
                "recent_logins": list(recent_logins),
                "recent_assessments":list(recent_assessments)
            }
        })

        return Response(response_data)

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
        """
        List trainer notifications.

        Query params:
        - box: sent | inbox | both  (default: sent)
        - search: str (subject/message/link contains)
        - date_from: YYYY-MM-DD (created_at >=)
        - date_to: YYYY-MM-DD (created_at <=)
        - from_admin: true|false (only show those sent_by staff/admin)
        """
        role = getattr(request.user, "role", None)
        if role != "trainer" and not request.user.is_staff:
            return Response(
                {"error": "Only trainers can view notifications here."},
                status=status.HTTP_403_FORBIDDEN
            )

        box = (request.query_params.get("box") or "sent").strip().lower()
        if box not in ("sent", "inbox", "both"):
            box = "sent"

        search = (request.query_params.get("search") or "").strip()
        date_from = (request.query_params.get("date_from") or "").strip()
        date_to = (request.query_params.get("date_to") or "").strip()
        from_admin = (request.query_params.get("from_admin") or "").strip().lower() in ("1", "true", "yes")

        paginator = SmallPageNumberPagination()

        # ---------- Base query builders ----------
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
                # treat staff as admin
                qs = qs.filter(Q(sent_by__is_staff=True) | Q(sent_by__role="admin"))
            return qs.order_by("-created_at", "-id")

        page_payload = {}

        if box in ("sent", "both"):
            sent_qs = (
                Notification.objects
                .filter(sent_by=request.user)
                .annotate(recipients_count=Count("notificationreceipt", distinct=True))
            )
            sent_qs = apply_common_filters(sent_qs)
            sent_page = paginator.paginate_queryset(sent_qs, request) if box == "sent" else list(sent_qs[:50])  # cap for "both"
            sent_ser = SentNotificationSerializer(sent_page, many=True)
            page_payload["sent"] = sent_ser.data

        if box in ("inbox", "both"):
            # Subquery to pull this trainer's read_at for each notification
            receipt_sq = NotificationReceipt.objects.filter(
                notification_id=OuterRef("pk"),
                user_id=request.user.id,
            ).values("read_at")[:1]

            # Also check existence to ensure we only fetch those addressed to this user
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
            # Expect your Inbox serializer to expose: id, subject, message, link, created_at,
            # sent_by (nested or username), my_read_at
            inbox_ser = InboxNotificationSerializer(inbox_page, many=True)
            page_payload["inbox"] = inbox_ser.data

        # If box is "sent" or "inbox", return a paginated response for that one box.
        # If box is "both", return a plain Response (no paginator merging across two lists).
        if box == "both":
            return Response(page_payload, status=200)
        else:
            # keep paginator behavior consistent for single box
            return paginator.get_paginated_response(page_payload.get(box, []))

    @swagger_auto_schema(
        operation_description="""
        Send notifications.

        Who can send:
        - trainer (role=trainer)
        - staff/admin (is_staff=True or role=admin)

        Modes:
        - individual: pass `usernames` (list)
        - group:
            audience: employee | trainee | trainer | both | all
            department (optional; applies to employees; defaults to trainer's department if available)
        """,
        request_body=TrainerNotificationRequestSerializer,
        responses={200: openapi.Response("OK"), 400: "Bad Request", 403: "Forbidden", 404: "Not Found"}
    )
    def post(self, request):
        role = getattr(request.user, "role", None)
        if role != "trainer" and not request.user.is_staff:
            return Response({"error": "Only trainers or staff can send notifications."}, status=status.HTTP_403_FORBIDDEN)

        ser = TrainerNotificationRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        subject    = data["subject"].strip()
        message    = data["message"].strip()
        link       = (data.get("link") or "").strip() or None
        notif_type = data["notification_type"]
        mode       = data["mode"]
        audience   = data["audience"].strip().lower()  # employee | trainee | trainer | both | all
        dept_arg   = (data.get("department") or "").strip() or None

        # Get trainer dept (fallback)
        trainer_dept = None
        try:
            tp = TrainerProfile.objects.only("department").get(user=request.user)
            trainer_dept = tp.department
        except TrainerProfile.DoesNotExist:
            pass

        base_q = Q(is_active=True)
        role_q = Q()

        if mode == "individual":
            usernames = data.get("usernames") or []
            if not usernames:
                return Response({"error": "`usernames` is required for individual mode."}, status=400)
            usernames = list({str(u).strip() for u in usernames if str(u).strip()})
            if not usernames:
                return Response({"error": "No valid usernames provided."}, status=400)
            qs = CustomUser.objects.filter(base_q, Q(username__in=usernames)).only("id", "email", "role")

        elif mode == "group":
            # Expand audience options
            wants_employee = audience in ("employee", "both", "all")
            wants_trainee  = audience in ("trainee", "both", "all")
            wants_trainer  = audience in ("trainer", "all")

            if wants_employee:
                if dept_arg:
                    role_q |= Q(role="employee", employee_profile__department=dept_arg)
                elif trainer_dept:
                    role_q |= Q(role="employee", employee_profile__department=trainer_dept)
                else:
                    role_q |= Q(role="employee")

            if wants_trainee:
                role_q |= Q(role="trainee")

            if wants_trainer:
                role_q |= Q(role="trainer")

            if role_q.children == []:
                return Response({"error": "Invalid audience for group mode."}, status=400)

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

        emp_count = sum(1 for r in roles if r == "employee")
        trn_count = sum(1 for r in roles if r == "trainee")
        tnr_count = sum(1 for r in roles if r == "trainer")

        with transaction.atomic():
            notif = Notification.objects.create(
                subject=subject,
                message=message,
                link=link,
                notification_type=notif_type,
                sent_by=request.user,
            )

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

        try:
            send_push_notification.delay(ids, subject, message)
        except Exception:
            pass

        for e in emails:
            try:
                send_notification_email.delay(e, subject, message)
            except Exception:
                continue

        return Response(
            {
                "message": f"Notification sent to {len(ids)} user(s).",
                "notification_id": notif.id,
                "counts": {"employees": emp_count, "trainees": trn_count, "trainers": tnr_count},
                "audience": audience,
                "mode": mode,
                "department_scope": dept_arg or trainer_dept or None,
            },
            status=200,
        )

class TrainingReportView(viewsets.ViewSet):
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
            # Get trainer's department
            try:
                trainer_profile = TrainerProfile.objects.get(user=user)
                trainer_department = trainer_profile.department
            except TrainerProfile.DoesNotExist:
                return Response(
                    {"error": "Trainer profile not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Map trainer department to trainee department
            # Development trainers see Training trainees
            # Shop Editing trainers see Shop Editor Training trainees
            # All other trainers see trainees from their same department
            department_mapping = {
                "Development": "Training",
                "Shop Editing": "Shop Editor Training"
            }
            trainee_department = department_mapping.get(trainer_department, trainer_department)
            
            # Get trainees from the mapped department
            trainee_user_ids = (
                TraineeProfile.objects
                .filter(department=trainee_department)
                .values_list('user_id', flat=True)
            )
            users = CustomUser.objects.filter(
                Q(id__in=trainee_user_ids) | Q(id=user.id, role='employee'),
                is_active=True
            ).distinct()
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
                # Check if trainer can view this trainee based on department mapping
                try:
                    trainer_profile = TrainerProfile.objects.get(user=requester)
                    trainee_profile = TraineeProfile.objects.get(user=target_user)
                    
                    # Map trainer department to trainee department
                    department_mapping = {
                        "Development": "Training",
                        "Shop Editing": "Shop Editor Training"
                    }
                    allowed_trainee_dept = department_mapping.get(
                        trainer_profile.department, 
                        trainer_profile.department
                    )
                    
                    # Check if trainee is in the allowed department
                    if trainee_profile.department != allowed_trainee_dept:
                        return Response(
                            {"error": "Unauthorized access - trainee not in your department"}, 
                            status=status.HTTP_403_FORBIDDEN
                        )
                except (TrainerProfile.DoesNotExist, TraineeProfile.DoesNotExist):
                    return Response(
                        {"error": "Profile not found"}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
            elif target_user.role == 'employee':
                # Trainers can view only their own employee account
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
    
class TrainerLibraryListView(BaseSLListView):
    required_role = "trainer"

class TrainerSOPListView(BaseSOPListView):
    REQUIRED_ROLE = "trainer"



class TrainerLessonProgressView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        # GET -> read serializer (includes names), POST -> write serializer
        return (
            TrainerLessonProgressReadSerializer
            if self.request.method == "GET"
            else TrainerLessonProgressWriteSerializer
        )

    def get_queryset(self):
        trainer = get_trainer_profile(self.request.user)
        if not trainer:
            return TrainerLessonProgress.objects.none()
        return (
            TrainerLessonProgress.objects
            .select_related("lesson", "lesson__course")   # <- important for names and performance
            .filter(trainer=trainer)
            .order_by("-last_accessed_at")
        )

class TrainerCourseProgressSummaryView(ListAPIView):
    """
    Per-course summary for signed-in trainer, using course_name/lesson_name.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        trainer = getattr(request.user, "trainer_profile", None)
        if not trainer:
            return Response([])

        courses = Courses.objects.filter(
            department=trainer.department,
            display_on_frontend=True,
            # is_approved=True,   # optional gate
        ).only("id", "course_name")

        lesson_counts = dict(
            CourseLesson.objects
            .filter(
                course__in=courses,
                display_on_frontend=True,
                # is_approved=True,  # optional gate
            )
            .values("course_id")
            .annotate(total=Count("id"))
            .values_list("course_id", "total")
        )

        completed_by_course = dict(
            TrainerLessonProgress.objects
            .filter(
                trainer=trainer,
                lesson__course__in=courses,
                lesson__display_on_frontend=True,
                # lesson__is_approved=True,  # optional gate
                status="completed",
            )
            .values("lesson__course_id")
            .annotate(done=Count("id"))
            .values_list("lesson__course_id", "done")
        )

        payload = []
        for c in courses:
            total = int(lesson_counts.get(c.id, 0) or 0)
            done = int(completed_by_course.get(c.id, 0) or 0)
            percent = int(round((done / total) * 100)) if total else 0
            payload.append({
                "course_id": c.id,               # DB pk (int)
                "course_code": c.course_id,      # your unique string code
                "course_name": c.course_name,
                "total_lessons": total,
                "completed_lessons": done,
                "completion_percent": percent,
            })

        payload.sort(key=lambda x: (-x["completion_percent"], x["course_name"].lower()))
        return Response(payload)


class TrainerLessonProgressDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_serializer_class(self):
        # GET -> read serializer, PATCH/PUT -> write serializer
        return (
            TrainerLessonProgressReadSerializer
            if self.request.method == "GET"
            else TrainerLessonProgressWriteSerializer
        )

    def get_queryset(self):
        trainer = getattr(self.request.user, "trainer_profile", None)
        if not trainer:
            return TrainerLessonProgress.objects.none()
        return (
            TrainerLessonProgress.objects
            .select_related("lesson", "lesson__course")
            .filter(trainer=trainer, lesson__course__department=trainer.department)
        )
    
class IsAuth(permissions.IsAuthenticated):
    pass

class TaskAssignmentViewSet(viewsets.ViewSet):
    """
    GET    /training/tasks/                     -> list (role-aware)
    POST   /training/tasks/                     -> create (trainer/admin)
    GET    /training/tasks/<pk>/                -> retrieve (role-aware)
    PATCH  /training/tasks/<pk>/                -> update (trainer/admin)
    POST   /training/tasks/<pk>/start/          -> assignee marks in-progress
    POST   /training/tasks/<pk>/complete/       -> trainer/admin closes as completed
    POST   /training/tasks/<pk>/cancel/         -> trainer/admin cancels
    POST   /training/tasks/<pk>/attach-submit/  -> assignee links a submission
    """
    permission_classes = [IsAuth]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def _base_qs(self):
        return TaskAssignment.objects.select_related("assigned_to", "created_by", "submission")

    def _trainer_profile(self, user):
        return getattr(user, "trainerprofile", None) or getattr(user, "trainer_profile", None)

    def _apply_filters(self, qs):
        p = self.request.query_params
        status_q   = (p.get("status") or "").strip().lower()
        dept_q     = (p.get("department") or "").strip()
        assignee_q = (p.get("assignee") or "").strip()
        overdue_q  = (p.get("overdue") or "").strip()  # "1" to filter overdue
        due_after  = (p.get("due_after") or "").strip()
        due_before = (p.get("due_before") or "").strip()

        if status_q in dict(TaskAssignment.STATUS_CHOICES):
            qs = qs.filter(status=status_q)
        if dept_q:
            qs = qs.filter(department__iexact=dept_q)
        if assignee_q:
            qs = qs.filter(assigned_to__username=assignee_q)
        if overdue_q == "1":
            qs = qs.filter(due_at__lt=timezone.now()).exclude(
                status__in=[TaskAssignment.STATUS_REVIEWED, TaskAssignment.STATUS_COMPLETED, TaskAssignment.STATUS_CANCELLED]
            )
        if due_after:
            qs = qs.filter(due_at__gte=due_after)
        if due_before:
            qs = qs.filter(due_at__lte=due_before)
        return qs

    # ---- list ----
    def list(self, request):
        user = request.user
        role = getattr(user, "role", None)

        if user.is_staff or getattr(user, "is_superuser", False):
            qs = self._apply_filters(self._base_qs()).order_by("-created_at")

        elif role == "trainer":
            tp = self._trainer_profile(user)
            q = Q()
            if tp and getattr(tp, "department", None):
                # Map trainer department to trainee department
                department_mapping = {
                    "Development": "Training",
                    "Shop Editing": "Shop Editor Training"
                }
                trainer_dept = str(tp.department)
                mapped_dept = department_mapping.get(trainer_dept, trainer_dept)
                q &= Q(department__iexact=mapped_dept)
            qs = self._apply_filters(self._base_qs().filter(q)).order_by("-created_at")

        elif role in ("trainee", "employee"):
            qs = self._apply_filters(self._base_qs().filter(assigned_to=user)).order_by("-created_at")

        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        ser = TaskAssignmentSerializer(qs, many=True)
        return Response(ser.data)

    # ---- create (trainer/admin) ----
    @swagger_auto_schema(request_body=TaskAssignmentCreateSerializer)
    def create(self, request):
        user = request.user
        if not (user.is_staff or getattr(user, "is_superuser", False) or getattr(user, "role", None) == "trainer"):
            return Response({"error": "Only trainers or admins can create tasks."}, status=status.HTTP_403_FORBIDDEN)

        ser = TaskAssignmentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(created_by=user)
        return Response(TaskAssignmentSerializer(obj).data, status=status.HTTP_201_CREATED)

    # ---- retrieve ----
    def retrieve(self, request, pk=None):
        user = request.user
        role = getattr(user, "role", None)
        try:
            obj = self._base_qs().get(pk=pk)
        except TaskAssignment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        if user.is_staff or getattr(user, "is_superuser", False):
            pass
        elif role == "trainer":
            tp = self._trainer_profile(user)
            dept = getattr(tp, "department", None) if tp else None
            if dept and obj.department:
                # Map trainer department to trainee department
                department_mapping = {
                    "Development": "Training",
                    "Shop Editing": "Shop Editor Training"
                }
                trainer_dept = str(dept)
                mapped_dept = department_mapping.get(trainer_dept, trainer_dept)
                if str(obj.department).lower() != mapped_dept.lower():
                    return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        elif role in ("trainee", "employee"):
            if obj.assigned_to_id != user.id:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        return Response(TaskAssignmentSerializer(obj).data)

    # ---- partial update (trainer/admin) ----
    def partial_update(self, request, pk=None):
        user = request.user
        role = getattr(user, "role", None)
        if not (user.is_staff or getattr(user, "is_superuser", False) or role == "trainer"):
            return Response({"error": "Only trainers or admins can update tasks."}, status=status.HTTP_403_FORBIDDEN)

        try:
            obj = TaskAssignment.objects.get(pk=pk)
        except TaskAssignment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check department authorization for trainers
        if role == "trainer" and not (user.is_staff or getattr(user, "is_superuser", False)):
            tp = self._trainer_profile(user)
            dept = getattr(tp, "department", None) if tp else None
            if dept and obj.department:
                # Map trainer department to trainee department
                department_mapping = {
                    "Development": "Training",
                    "Shop Editing": "Shop Editor Training"
                }
                trainer_dept = str(dept)
                mapped_dept = department_mapping.get(trainer_dept, trainer_dept)
                if str(obj.department).lower() != mapped_dept.lower():
                    return Response({"error": "Unauthorized - task not in your department"}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # Allow editing common fields; status may be controlled via actions
        allowed = {"title", "instructions", "department", "priority", "assigned_to", "due_at", "attachment", "max_marks", "requires_submission", "status"}
        data = {k: v for k, v in request.data.items() if k in allowed}
        for f, v in data.items():
            setattr(obj, f, v)
        obj.save()
        return Response(TaskAssignmentSerializer(obj).data)

    # ---- assignee starts work ----
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        user = request.user
        try:
            obj = TaskAssignment.objects.get(pk=pk, assigned_to=user)
        except TaskAssignment.DoesNotExist:
            return Response({"error": "Not found or not your task."}, status=status.HTTP_404_NOT_FOUND)

        if obj.status == TaskAssignment.STATUS_ASSIGNED:
            obj.status = TaskAssignment.STATUS_IN_PROGRESS
            obj.save(update_fields=["status", "updated_at"])
        return Response(TaskAssignmentSerializer(obj).data)

    # ---- attach existing submission (assignee) ----
    @action(detail=True, methods=["post"], url_path="attach-submit")
    def attach_submit(self, request, pk=None):
        user = request.user
        try:
            obj = TaskAssignment.objects.get(pk=pk, assigned_to=user)
        except TaskAssignment.DoesNotExist:
            return Response({"error": "Not found or not your task."}, status=status.HTTP_404_NOT_FOUND)

        ser = LinkSubmissionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sub = TraineeTaskSubmission.objects.get(pk=ser.validated_data["submission_id"])

        # Security: only allow linking the assignee's own submission
        if sub.trainee_id != user.id:
            return Response({"error": "You can only link your own submission."}, status=status.HTTP_403_FORBIDDEN)

        obj.submission = sub
        # mirror state with submission
        if sub.status == sub.STATUS_REVIEWED:
            obj.status = TaskAssignment.STATUS_REVIEWED
        else:
            obj.status = TaskAssignment.STATUS_SUBMITTED
        obj.save(update_fields=["submission", "status", "updated_at"])
        return Response(TaskAssignmentSerializer(obj).data)

    # ---- trainer/admin closes as completed ----
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        user = request.user
        role = getattr(user, "role", None)
        if not (user.is_staff or getattr(user, "is_superuser", False) or role == "trainer"):
            return Response({"error": "Only trainers or admins can complete tasks."}, status=status.HTTP_403_FORBIDDEN)

        try:
            obj = TaskAssignment.objects.get(pk=pk)
        except TaskAssignment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check department authorization for trainers
        if role == "trainer" and not (user.is_staff or getattr(user, "is_superuser", False)):
            tp = self._trainer_profile(user)
            dept = getattr(tp, "department", None) if tp else None
            if dept and obj.department:
                # Map trainer department to trainee department
                department_mapping = {
                    "Development": "Training",
                    "Shop Editing": "Shop Editor Training"
                }
                trainer_dept = str(dept)
                mapped_dept = department_mapping.get(trainer_dept, trainer_dept)
                if str(obj.department).lower() != mapped_dept.lower():
                    return Response({"error": "Unauthorized - task not in your department"}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        obj.status = TaskAssignment.STATUS_COMPLETED
        obj.save(update_fields=["status", "updated_at"])
        return Response(TaskAssignmentSerializer(obj).data)

    # ---- trainer/admin cancels ----
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        user = request.user
        role = getattr(user, "role", None)
        if not (user.is_staff or getattr(user, "is_superuser", False) or role == "trainer"):
            return Response({"error": "Only trainers or admins can cancel tasks."}, status=status.HTTP_403_FORBIDDEN)

        try:
            obj = TaskAssignment.objects.get(pk=pk)
        except TaskAssignment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check department authorization for trainers
        if role == "trainer" and not (user.is_staff or getattr(user, "is_superuser", False)):
            tp = self._trainer_profile(user)
            dept = getattr(tp, "department", None) if tp else None
            if dept and obj.department:
                # Map trainer department to trainee department
                department_mapping = {
                    "Development": "Training",
                    "Shop Editing": "Shop Editor Training"
                }
                trainer_dept = str(dept)
                mapped_dept = department_mapping.get(trainer_dept, trainer_dept)
                if str(obj.department).lower() != mapped_dept.lower():
                    return Response({"error": "Unauthorized - task not in your department"}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        obj.status = TaskAssignment.STATUS_CANCELLED
        obj.save(update_fields=["status", "updated_at"])
        return Response(TaskAssignmentSerializer(obj).data)