from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.db.models.functions import TruncDate
from user.models import (
    TrainerProfile,TraineeProfile, CustomUser,Courses,CourseLesson,Microplanner,Macroplanner,Assessment,AssessmentReport,EvaluationRemark,TrainingReport,UserLoginActivity,QueryResponse,
    Query,EmployeeProfile,Notification,NotificationReceipt,TraineeLessonCompletion,EmployeeLessonCompletion
)
from user.serializers import (
    TrainerSerializer,CourseSerializer, CourseLessonSerializer, MacroplannerSerializer, MicroplannerSerializer,AssessmentSerializer,AssessmentReportSerializer,
    EvaluationRemarkSerializer,TrainingReportSerializer,UserLoginActivitySerializer,QueryResponseSerializer,QuerySerializer,
    EmployeeSerializer,TrainerNotificationRequestSerializer,SentNotificationSerializer,ActiveUserSerializer
)
from rest_framework.generics import ListCreateAPIView,RetrieveUpdateAPIView, ListAPIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework import status
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

class TrainerDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            trainer_obj = TrainerProfile.objects.get(user=request.user)
            department = trainer_obj.department
        except TrainerProfile.DoesNotExist:
            return Response({"error": "Trainer profile not found."}, status=404)

        # Profile data
        profile_data = TrainerSerializer(trainer_obj).data

        # Count of trainees assigned to this trainer
        trainee_qs = CustomUser.objects.filter(
            trainee_profile__trainer=request.user
        )
        total_trainees = trainee_qs.count()

        # Courses (we can later add filtering by department or trainer-assigned logic)
        courses = Courses.objects.filter(created_by=request.user)
        course_count = courses.count()

        # Active users in the trainer's department
        active_users = get_active_users(department) if department else CustomUser.objects.none()
        active_users_data = ActiveUserSerializer(active_users, many=True).data
        active_count = active_users.count()

        return Response({
            "profile": profile_data,
            "trainee_count": total_trainees,
            "course_count": course_count,
            "courses": list(courses.values("course_id", "course_name", "department", "is_approved")),
            "active_count": active_count,
            "active_users": active_users_data,
        }, status=200)


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

        students = EmployeeProfile.objects.filter(department=department_instance).only("user__username")

        recent_logins = UserLoginActivity.objects.filter(
            login_username__in=students.values_list("user__username", flat=True)
        ).annotate(
            login_date=TruncDate("login_datetime")
        ).values("login_username", "login_date").order_by("-login_datetime")[:5]

        response_data=({
            "recent_activity": {
                "recent_logins": list(recent_logins),
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
            tp = TrainerProfile.objects.only("department").get(user=request.user)
            trainer_dept = tp.department
        except TrainerProfile.DoesNotExist:
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

# class TrainingReportView(viewsets.ViewSet):
#     permission_classes = [IsAuthenticated]

#     def list(self, request):
#         user = request.user  # CustomUser instance
#         report_data = []

#         if user.role == 'admin':
#             users = CustomUser.objects.filter(Q(role='trainee') | Q(role='employee')).exclude(is_active=False)
#         elif user.role == 'trainer':
#             try:
#                 trainees = TraineeProfile.objects.filter(trainer_id=user.id).values_list('user_id', flat=True)
#                 users = CustomUser.objects.filter(
#                     Q(id__in=trainees) | (Q(role='employee') & Q(id=user.id))
#                 ).exclude(is_active=False)
#             except Exception as e:
#                 return Response({"error": f"Error fetching trainees: {str(e)}"}, status=status.HTTP500_INTERNAL_SERVER_ERROR)
#         else:
#             return Response({"error": "Unauthorized access"}, status=status.HTTP403_FORBIDDEN)

#         for user_instance in users:
#             completed_lessons = []
#             profile = None
#             if user_instance.role == 'trainee':
#                 profile = TraineeProfile.objects.filter(user=user_instance).first()
#                 if profile:
#                     completed_lessons = TraineeLessonCompletion.objects.filter(trainee=profile)
#             elif user_instance.role == 'employee':
#                 profile = EmployeeProfile.objects.filter(user=user_instance).first()
#                 if profile:
#                     completed_lessons = EmployeeLessonCompletion.objects.filter(employee=profile)
#             name = profile.name if profile else "N/A"
#             serializer = TrainingReportSerializer({
#                 'user_id': user_instance.id,
#                 'username': user_instance.username,
#                 'role': user_instance.role,
#                 'name': name,
#                 'completed_lessons': completed_lessons
#             })
#             report_data.append(serializer.data)

#         return Response(report_data, status=status.HTTP_200_OK)
# class TrainingReportView(viewsets.ViewSet):
#     permission_classes = [IsAuthenticated]

#     def list(self, request):
#         user = request.user  # CustomUser instance
#         report_data = []

#         if user.role == 'admin':
#             users = CustomUser.objects.filter(Q(role='trainee') | Q(role='employee')).exclude(is_active=False)
#         elif user.role == 'trainer':
#             try:
#                 trainees = TraineeProfile.objects.filter(trainer_id=user.id).values_list('user_id', flat=True)
#                 users = CustomUser.objects.filter(
#                     Q(id__in=trainees) | (Q(role='employee') & Q(id=user.id))
#                 ).exclude(is_active=False)
#             except Exception as e:
#                 return Response({"error": f"Error fetching trainees: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#         else:
#             return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)

#         for user_instance in users:
#             completed_lessons = []
#             profile = None
#             if user_instance.role == 'trainee':
#                 profile = TraineeProfile.objects.filter(user=user_instance).first()
#                 if profile:
#                     completed_lessons = TraineeLessonCompletion.objects.filter(trainee=profile)
#             elif user_instance.role == 'employee':
#                 profile = EmployeeProfile.objects.filter(user=user_instance).first()
#                 if profile:
#                     completed_lessons = EmployeeLessonCompletion.objects.filter(employee=profile)
#             name = profile.name if profile else "N/A"
#             serializer = TrainingReportSerializer({
#                 'user_id': user_instance.id,
#                 'username': user_instance.username,
#                 'role': user_instance.role,
#                 'name': name,
#                 'completed_lessons': completed_lessons
#             })
#             report_data.append(serializer.data)

#         return Response(report_data, status=status.HTTP_200_OK)

#     def retrieve(self, request, pk=None):
#         """
#         Fetch the complete training report for a specific user.
#         """
#         user = request.user
#         try:
#             target_user = CustomUser.objects.get(id=pk)
#         except CustomUser.DoesNotExist:
#             return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

#         # Authorization check
#         if user.role == 'admin':
#             pass  # Admin can view any user's report
#         elif user.role == 'trainer':
#             if target_user.role == 'trainee':
#                 if not TraineeProfile.objects.filter(user=target_user, trainer_id=user.id).exists():
#                     return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
#             elif target_user.role == 'employee' and target_user.id != user.id:
#                 return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
#         else:
#             return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)

#         # Fetch detailed report
#         completed_lessons = []
#         profile = None
#         if target_user.role == 'trainee':
#             profile = TraineeProfile.objects.filter(user=target_user).first()
#             if profile:
#                 completed_lessons = TraineeLessonCompletion.objects.filter(trainee=profile).select_related('lesson')
#         elif target_user.role == 'employee':
#             profile = EmployeeProfile.objects.filter(user=target_user).first()
#             if profile:
#                 completed_lessons = EmployeeLessonCompletion.objects.filter(employee=profile).select_related('lesson')

#         name = profile.name if profile else "N/A"
#         detailed_report = {
#             'user_id': target_user.id,
#             'username': target_user.username,
#             'role': target_user.role,
#             'name': name,
#             'employee_id': getattr(profile, 'employee_id', 'N/A') if profile else 'N/A',
#             'department': getattr(profile, 'department', 'N/A') if profile else 'N/A',
#             'designation': getattr(profile, 'designation', 'N/A') if profile else 'N/A',
#             'trainer_name': getattr(profile, 'trainer__name', 'N/A') if profile and hasattr(profile, 'trainer') else 'N/A',
#             'completed_lessons': [
#                 {
#                     'lesson_title': lesson.lesson.title,
#                     'completed': lesson.completed,
#                     'completed_at': lesson.completed_at,
#                     'duration': lesson.duration if hasattr(lesson, 'duration') else 'N/A',
#                     'score': lesson.score if hasattr(lesson, 'score') else 'N/A'
#                 } for lesson in completed_lessons
#             ]
#         }

#         serializer = TrainingReportSerializer(detailed_report)
#         return Response(serializer.data, status=status.HTTP_200_OK)
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