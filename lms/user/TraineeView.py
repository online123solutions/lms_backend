from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ViewSet as viewsets_ViewSet
from rest_framework.permissions import IsAuthenticated as permissions_IsAuthenticated
from .serializers import (
    SubjectSerializer, TraineeSerializer, LessonSerializer,QueryResponseSerializer, QuerySerializer,ContentEndSerializer,
    ContentStartSerializer,MacroplannerSerializer,MicroplannerSerializer,UserLoginActivitySerializer,NotificationReceiptSerializer,
    ActiveQuizListSerializer,TraineeProgressSerializer,TraineeFeedbackSerializer,TraineeTaskSubmissionSerializer,TraineeTaskReviewSerializer,
    BannerSerializer,ConcernAssignSerializer,ConcernCreateSerializer,ConcernDetailSerializer,ConcernListSerializer,ConcernStatusSerializer,
    ConcernCommentSerializer,ConcernCommentCreateSerializer,ActiveUserSerializer
)
from .models import (
    Subject, Lesson,TraineeProfile, TrainerProfile, UserLoginActivity,Query,Macroplanner, Microplanner,CustomUser,AssessmentReport,NotificationReceipt,
    TraineeLessonCompletion,TraineeTaskSubmission,Banner,Concern,ConcernComment
)
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema # type: ignore
from rest_framework.generics import ListAPIView
from django.utils.timezone import now
from quiz.models import Result, Quiz
from quiz.serializers import QuizSerializer
from rest_framework.exceptions import NotFound,PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from collections import defaultdict
from datetime import timedelta
from django.db.models import Max,Avg,Count,Q
from django.db.models import Exists, OuterRef

# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Subject, TraineeProfile, EmployeeProfile
from .serializers import SubjectSerializer
from .views import BaseSOPListView,BaseSLListView
from .utils import get_active_users
from rest_framework import viewsets,generics, permissions
from rest_framework.decorators import action
import logging
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.contrib.sessions.models import Session


class SubjectListAPIView(APIView):
    """
    GET /subjects/
    Returns subjects for the authenticated user's department.
    Works for both TraineeProfile and EmployeeProfile.
    """
    permission_classes = [IsAuthenticated]

    def _get_user_department(self, user):
        # Try trainee first
        try:
            return TraineeProfile.objects.only("department").get(user=user).department
        except TraineeProfile.DoesNotExist:
            pass
        # Then employee
        try:
            return EmployeeProfile.objects.only("department").get(user=user).department
        except EmployeeProfile.DoesNotExist:
            pass
        return None

    def get(self, request):
        department = self._get_user_department(request.user)
        if department is None:
            return Response(
                {"error": "No trainee/employee profile found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Filter subjects for that department (also show only those meant for frontend)
        qs = (
            Subject.objects
            .filter(department=department, display_on_frontend=True)
            .order_by("name")
        )

        # Prefer returning 200 with an empty list (easier for frontends)
        serializer = SubjectSerializer(qs, many=True, context={"request": request})
        return Response({"subjects": serializer.data}, status=status.HTTP_200_OK)


class LessonListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_user_department(self, user):
        # Try trainee first
        try:
            return TraineeProfile.objects.only("department").get(user=user).department
        except TraineeProfile.DoesNotExist:
            pass
        # Then employee
        try:
            return EmployeeProfile.objects.only("department").get(user=user).department
        except EmployeeProfile.DoesNotExist:
            pass
        return None

    def get(self, request, slug):
        try:
            department = self._get_user_department(request.user)
            subject = get_object_or_404(Subject, slug=slug, display_on_frontend=True)

            filtered_lessons = Lesson.objects.filter(
                department=department, 
                subject=subject, 
                display_on_frontend=True
            )

            if not filtered_lessons.exists():
                return Response({
                    'message': f'No lessons found for subject "{subject.name}" in your department.',
                    'subject': subject.name,
                    'subject_slug': subject.slug,
                    'department': department,
                    'subject_display_on_frontend': subject.display_on_frontend
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = LessonSerializer(filtered_lessons, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except TraineeProfile.DoesNotExist:
            return Response({"error": "User profile does not exist."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LessonDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            lesson = get_object_or_404(Lesson, slug=slug, display_on_frontend=True)

            lesson_data = {
                'id': lesson.id,
                'name': lesson.name,
                'lesson_id': lesson.lesson_id,
                'department': lesson.department,
                'subject': lesson.subject.name,
                'position': lesson.position,
                'tutorial_video': lesson.tutorial_video,
                'quiz': lesson.quiz,
                'content': lesson.content,
                'editor': lesson.editor,
                'lesson_pdfs': lesson.lesson_pdfs,
                'display_on_frontend': lesson.display_on_frontend,
                'mark_as_completed': lesson.mark_as_completed,
            }

            return Response({'lesson': lesson_data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class TraineeDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get_trainee_reports(self, student, quiz_type):
        from quiz.models import Result,Answer,ResultAnswer

        results = Result.objects.filter(user=student.user, quiz__quiz_type=quiz_type)
        quiz_ids = results.values_list("quiz_id", flat=True)

        reports = AssessmentReport.objects.filter(
            quiz__id__in=quiz_ids,
            quiz__quiz_type=quiz_type
        )

        report_list = []
        for report in reports:
            quiz=report.quiz
            trainee_result = results.filter(quiz=quiz).order_by('-date_attempted').first()
            if not trainee_result:
                continue

            total_questions = quiz.no_of_questions
            correct_questions = getattr(trainee_result, 'correct_questions', None) or 0
            wrong_questions = getattr(trainee_result, 'wrong_questions', None) or 0
            unattempted_questions = getattr(trainee_result, 'unattempted_questions', None) or 0
            trainee_score = trainee_result.score

            # Calculate average score for the quiz across all users
            avg_score = Result.objects.filter(quiz=quiz).aggregate(avg=Avg('score'))['avg'] or 0
            highest_score = Result.objects.filter(quiz=quiz).aggregate(highest=Max('score'))['highest'] or 0

            feedback = []
            answers = ResultAnswer.objects.filter(result=trainee_result).select_related('question', 'selected_answer')

            for ans in answers:
                correct_answer_obj = Answer.objects.filter(question=ans.question, correct=True).first()
                correct_answer_text = correct_answer_obj.answer if correct_answer_obj else "N/A"
                selected_answer_text = ans.selected_answer.answer if ans.selected_answer else None

                feedback.append({
                    "question": ans.question.question,
                    "correct_answer": correct_answer_text,
                    "trainee_answer": selected_answer_text,
                    "is_correct": ans.is_correct
                })

            report_list.append({
            "exam_name": quiz.quiz_name,
            "quiz_type": quiz.quiz_type,
            "topic": quiz.topic,
            "total_questions": total_questions,
            "correct_questions": correct_questions,
            "wrong_questions": wrong_questions,
            "unattempted_questions": unattempted_questions,
            "trainee_score": round(trainee_score, 2),
            "average_score": round(avg_score, 2),
            "highest_score": round(highest_score, 2),
            "certificate_url": trainee_result.certificate.url if trainee_result.certificate else None,
            "questions_feedback": feedback 
        })

        return report_list


    def get(self, request, username):
        try:
            user = get_object_or_404(CustomUser, username=username)
            trainee_obj = get_object_or_404(TraineeProfile, user__username=username)

            profile_data = TraineeSerializer(trainee_obj).data

            # login_count = UserLoginActivity.objects.filter(login_username=request.user).count()
            subjects= Subject.objects.filter(department=trainee_obj.department)
            subjects_count = subjects.count()

            subjects_data = SubjectSerializer(subjects, many=True).data

            quizzes = Quiz.objects.filter(department=trainee_obj.department, start_date__lte=now(), end_date__gte=now())
            quiz_serializer = QuizSerializer(quizzes, many=True)

            login_count= UserLoginActivity.objects.filter(login_username=user).count()
            homework_reports = self.get_trainee_reports(trainee_obj, "homework")
            pre_assessment_reports = self.get_trainee_reports(trainee_obj, "pre-assessment")
            post_assessment_reports = self.get_trainee_reports(trainee_obj, "post-assessment")
            daily_quiz_reports = self.get_trainee_reports(trainee_obj, "daily-quiz")
            weekly_quiz_reports = self.get_trainee_reports(trainee_obj, "weekly-quiz")
            monthly_quiz_reports = self.get_trainee_reports(trainee_obj, "monthly-quiz")
            final_exam_reports = self.get_trainee_reports(trainee_obj, "final_exam")

            active_homework= Quiz.objects.filter(
                department=trainee_obj.department,
                start_date__lte=now(),
                end_date__gte=now(),
            )
            active_homework = QuizSerializer(active_homework, many=True)

            # Lesson completion tracking
            completions = TraineeLessonCompletion.objects.filter(
                trainee=trainee_obj,
                completed=True
            )
            completed_lessons_count = completions.count()
            completed_lesson_ids = list(completions.values_list('lesson__id', flat=True))

            # Completed lessons per subject (aggregation)
            completed_per_subject = completions.values(
                'lesson__subject__name'
            ).annotate(
                completed_count=Count('lesson__subject__name')
            ).order_by('lesson__subject__name')

            completed_per_subject_data = {
                item['lesson__subject__name']: item['completed_count']
                for item in completed_per_subject
            }


            # ✅ Dedicated ACTIVE QUIZZES (live now) with attempt flag
            attempted_subq = Result.objects.filter(
                user=trainee_obj.user, quiz=OuterRef("pk")
            )
            active_quizzes_qs = (
                Quiz.objects
                .filter(
                    department=trainee_obj.department,
                    start_date__lte=now(),
                    end_date__gte=now(),
                )
                .annotate(has_attempted=Exists(attempted_subq))
                .order_by("-start_date")
            )
            active_quizzes_data = ActiveQuizListSerializer(
                active_quizzes_qs, many=True, context={"request": request}
            ).data
            
            # Get all active users without department filtering
            active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
            user_ids = {
                s.get_decoded().get('_auth_user_id')
                for s in active_sessions
                if '_auth_user_id' in s.get_decoded()
            }
            if user_ids:
                active_users = CustomUser.objects.filter(
                    id__in=user_ids
                ).select_related("trainee_profile", "employee_profile").distinct()
                active_users_data = ActiveUserSerializer(active_users, many=True).data
                active_count = active_users.count()
            else:
                active_users_data = []
                active_count = 0

            return Response({
                "profile": profile_data,
                "subjects": subjects_data,
                "subjects_count": subjects_count,
                "quizzes": quiz_serializer.data,
                "active_quizzes": active_quizzes_data,  
                "login_count": login_count,
                "homework_reports": homework_reports,
                "pre_assessment_reports": pre_assessment_reports,
                "post_assessment_reports": post_assessment_reports,
                "daily_quiz_reports": daily_quiz_reports,
                "weekly_quiz_reports": weekly_quiz_reports,
                "monthly_quiz_reports": monthly_quiz_reports,
                "final_exam_reports": final_exam_reports,
                "active_homework": active_homework.data,
                "completed_lessons_count": completed_lessons_count,
                "completed_lesson_ids": completed_lesson_ids,
                "completed_per_subject": completed_per_subject_data,
                "active_count": active_count,
                "active_users": active_users_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class AvailableQuizListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuizSerializer

    def get_queryset(self):
        user = self.request.user

        try:
            trainee = TraineeProfile.objects.get(user=user)
        except TraineeProfile.DoesNotExist:
            raise NotFound('Trainee profile not found.')

        attempted_quiz_ids = Result.objects.filter(user=user).values_list("quiz_id", flat=True)

        quizzes = Quiz.objects.filter(
            department=trainee.department,
            start_date__lte=now(),
            end_date__gte=now()
        ).exclude(id__in=attempted_quiz_ids)

        return quizzes
    
class TraineeQueryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            trainee_profile = get_object_or_404(TraineeProfile, user=request.user)

            queries = Query.objects.filter(raised_by=request.user)
            serializer = QuerySerializer(queries, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except TraineeProfile.DoesNotExist:
            return Response({"error": "No TraineeProfile matches the given query."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class TraineeQueryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes= [MultiPartParser, FormParser]

    @swagger_auto_schema(request_body=QuerySerializer)
    def post(self, request):
        serializer = QuerySerializer(data=request.data)
        if serializer.is_valid():
            query=serializer.save(raised_by=request.user)
            query.notify_trainer()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TraineeQueryResponseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(request_body=QueryResponseSerializer)
    def post(self, request, query_id):
        query = get_object_or_404(Query, id=query_id)

        # Trainees can respond to their own queries or queries assigned to them
        if request.user != query.raised_by and request.user != query.assigned_trainer:
            return Response({"error": "You are not authorized to respond to this query."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = QueryResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # <— surface exact error if any
        instance = serializer.save(query=query, responder=request.user)  # <— server sets responder
        return Response(QueryResponseSerializer(instance).data, status=status.HTTP_201_CREATED)
    

class ContentStartView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(request_body=ContentStartSerializer)
    def post(self, request):
        content_viewed = request.data.get("content_viewed")
        start_time = request.data.get("start_time")
        
        # Find or create the login activity for the current user
        user_activity = UserLoginActivity.objects.filter(
            user=request.user,
            content_viewed=content_viewed,
            content_start_time__isnull=True
        ).first()

        if user_activity:
            user_activity.content_start_time = start_time
            user_activity.save()
        
        return Response({"message": "Content start time tracked."}, status=status.HTTP_200_OK)

class ContentEndView(APIView):
    def post(self, request):
        # Deserialize the request data
        serializer = ContentEndSerializer(data=request.data)

        # Validate the data
        if serializer.is_valid():
            content_viewed = serializer.validated_data["content_viewed"]
            end_time = serializer.validated_data["end_time"]
            
            # Find the login activity where the content is being viewed
            user_activity = UserLoginActivity.objects.filter(
                user=request.user,
                content_viewed=content_viewed,
                content_end_time__isnull=True
            ).first()

            if user_activity:
                user_activity.content_end_time = end_time
                user_activity.save()

                # Check if it's saved successfully
                print(f"End time saved for {content_viewed}: {end_time}")

            return Response({"message": "Content end time tracked."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class TraineeMacroplannerListAPIView(APIView):
    """
    GET /trainee/macroplanners/
    Returns macroplanners scoped to the authenticated trainee's department
    with controlled cross-department visibility.
    """
    permission_classes = [IsAuthenticated]

    # 🔥 Department visibility mapping
    TRAINEE_DEPARTMENT_ACCESS_MAP = {
        "Training": ["Training", "Development"],
        "Shop Editor Training": ["Shop Editor Training", "Shop Editing"],
    }

    def get(self, request):

        # Ensure only trainees access this
        if request.user.role != "trainee":
            return Response(
                {"detail": "Only trainees can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get trainee profile
        try:
            trainee = (
                TraineeProfile.objects
                .select_related("user")
                .get(user=request.user)
            )
        except TraineeProfile.DoesNotExist:
            return Response(
                {"detail": "Trainee profile not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        trainee_department = trainee.department

        # Get allowed departments
        allowed_departments = self.TRAINEE_DEPARTMENT_ACCESS_MAP.get(
            trainee_department,
            [trainee_department]  # fallback: only own department
        )

        # Fetch macroplanners
        qs = (
            Macroplanner.objects
            .filter(
                department__in=allowed_departments,
                role=request.user.role
            )
            .order_by("-id")
        )

        serializer = MacroplannerSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class TraineeMicroplannerListAPIView(APIView):
    """
    GET /trainee/microplanners/
    Returns microplanners scoped to the authenticated trainee's department.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Ensure the requester has a TraineeProfile
        try:
            trainee = TraineeProfile.objects.select_related("user").get(user=request.user)
        except TraineeProfile.DoesNotExist:
            return Response(
                {"detail": "Trainee profile not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Fetch microplanners for trainee's department AND Development department
        qs = (
            Microplanner.objects
            .filter(
                Q(department=trainee.department),
                role=request.user.role
            )
            .order_by("-id")  # or "-created_at" if available
        )

        serializer = MicroplannerSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TraineeLoginActivityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            trainee_profile = TraineeProfile.objects.get(user=user)
        except TraineeProfile.DoesNotExist:
            return Response(
                {"message": "You do not have permission to view this page."},
                status=status.HTTP_403_FORBIDDEN
            )

        login_activities = UserLoginActivity.objects.filter(
            login_username=user.username
        ).order_by('login_datetime') 

        serializer = UserLoginActivitySerializer(login_activities, many=True)
        raw_data = serializer.data

        date_summary = defaultdict(lambda: {"login_count": 0, "time_spent_minutes": 0})
        prev_login_time = None
        max_session_duration = timedelta(minutes=30)

        for activity in login_activities:
            login_time = activity.login_datetime
            date_str = login_time.date().isoformat()
            date_summary[date_str]["login_count"] += 1

            if prev_login_time:
                session_duration = login_time - prev_login_time
                if session_duration > timedelta(seconds=0):
                    estimated = min(session_duration, max_session_duration)
                    date_summary[prev_login_time.date().isoformat()]["time_spent_minutes"] += int(estimated.total_seconds() / 60)

            prev_login_time = login_time

        # Add last session time as 10 minutes (assumed)
        if prev_login_time:
            date_str = prev_login_time.date().isoformat()
            date_summary[date_str]["time_spent_minutes"] += 10

        login_summary = [
            {
                "date": date,
                "login_count": summary["login_count"],
                "time_spent_minutes": summary["time_spent_minutes"]
            }
            for date, summary in sorted(date_summary.items())
        ]

        # Add user_id to login history
        for record in raw_data:
            record["user_id"] = user.id

        return Response({
            "trainee_profile": {
                "name": trainee_profile.name,
                "department": trainee_profile.department,
            },
            "total_logins": login_activities.count(),
            "login_summary": login_summary,
            # "login_history": raw_data
        }, status=status.HTTP_200_OK)
    
class BaseUserNotificationsView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationReceiptSerializer

    def get_queryset(self):
        qs = NotificationReceipt.objects.select_related('notification', 'notification__sent_by') \
                                        .filter(user=self.request.user) \
                                        .order_by('-delivered_at')
        unread = self.request.query_params.get('unread')
        if unread in ('1', 'true', 'True'):
            qs = qs.filter(is_read=False)
        return qs


class TraineeNotificationsView(BaseUserNotificationsView):
    def list(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'trainee':
            return Response({"error": "Not a trainee."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)
        

class TraineeSOPListView(BaseSOPListView):
    REQUIRED_ROLE = "trainee"

class TraineeLibraryListView(BaseSLListView):
    required_role = "trainee"

class TraineeProgressViewSet(viewsets.ViewSet):
    """
    GET /api/training/trainee-progress/          -> progress for current user (if trainee)
    GET /api/training/trainee-progress/<user_id> -> progress for a specific trainee (admin/trainer)
    """
    permission_classes = [IsAuthenticated]

    from django.db.models import Count, Max

    def _build_progress(self, target_user):
        # ---- profile ----
        profile = (
            TraineeProfile.objects
            .select_related('user', 'trainer')
            .filter(user=target_user)
            .first()
        )
        if not profile:
            return {"error": "Trainee profile not found"}

        # ---- all lessons grouped by subject (filtered by trainee's department) ----
        lessons_by_subject = (
            Lesson.objects
            .filter(department=profile.department)
            .values('subject_id', 'subject__name')
            .annotate(total=Count('id'))
        )
        totals_map = {r['subject_id']: r['total'] for r in lessons_by_subject}
        names_map  = {r['subject_id']: r['subject__name'] for r in lessons_by_subject}

        # ---- completed lessons for this trainee ----
        comp_qs = (
            TraineeLessonCompletion.objects
            .filter(trainee=profile, completed=True)
            .select_related('lesson__subject')
        )
        completed_group = (
            comp_qs.values('lesson__subject_id')
                .annotate(
                    completed=Count('lesson_id'),
                    last_completed_at=Max('completed_at')
                )
        )
        completed_map = {
            r['lesson__subject_id']: {
                "completed": r['completed'],
                "last_completed_at": r['last_completed_at']
            }
            for r in completed_group
        }

        # ---- build subject breakdown ----
        subjects_out = []
        for subject_id, total in totals_map.items():
            done = completed_map.get(subject_id, {}).get("completed", 0)
            last = completed_map.get(subject_id, {}).get("last_completed_at")
            pending = max(total - done, 0)
            pct = round((done / total) * 100.0, 2) if total else 0.0
            subjects_out.append({
                "subject_id": subject_id,
                "subject_name": names_map.get(subject_id, "Unknown"),
                "total_lessons": total,
                "completed_lessons": done,
                "pending_lessons": pending,
                "progress_pct": pct,
                "last_completed_at": last,
            })

        # ---- overall ----
        total_lessons = sum(s["total_lessons"] for s in subjects_out)
        total_done    = sum(s["completed_lessons"] for s in subjects_out)
        total_pending = max(total_lessons - total_done, 0)
        total_pct     = round((total_done / total_lessons) * 100.0, 2) if total_lessons else 0.0

        return {
            "user_id": target_user.id,
            "username": target_user.username,
            "name": getattr(profile, "name", target_user.get_full_name() or target_user.username),
            "totals": {
                "subjects_total": len(subjects_out),
                "lessons_total": total_lessons,
                "lessons_completed": total_done,
                "lessons_pending": total_pending,
                "progress_pct": total_pct,
            },
            "subjects": subjects_out,
        }

    # /api/training/trainee-progress/
    def list(self, request):
        if request.user.role != "trainee":
            return Response({"error": "Only trainees can access their own progress here."},
                            status=status.HTTP_403_FORBIDDEN)
        data = self._build_progress(request.user)
        if "error" in data:
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(TraineeProgressSerializer(data).data)

    # /api/training/trainee-progress/<pk>/
    def retrieve(self, request, pk=None):
        # admin -> any trainee; trainer -> only assigned trainees
        try:
            target = CustomUser.objects.get(id=pk, role='trainee', is_active=True)
        except CustomUser.DoesNotExist:
            return Response({"error": "Trainee not found"}, status=404)

        if request.user.role == "admin":
            pass
        elif request.user.role == "trainer":
            if not TraineeProfile.objects.filter(user=target, trainer_id=request.user.id).exists():
                return Response({"error": "Unauthorized"}, status=403)
        else:
            return Response({"error": "Unauthorized"}, status=403)

        data = self._build_progress(target)
        if "error" in data:
            return Response(data, status=404)
        return Response(TraineeProgressSerializer(data).data)
    
class TraineeFeedbackCreateView(generics.CreateAPIView):
    serializer_class = TraineeFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Return serializer with trainer options for form rendering"""
        serializer = self.get_serializer()
        data = serializer.data
        
        # Manually add trainers list since SerializerMethodField might not work without instance
        trainers = CustomUser.objects.filter(
            role='trainer',
            is_active=True
        ).select_related('trainer_profile').order_by('username')

        trainer_list = []
        for trainer in trainers:
            try:
                trainer_profile = trainer.trainer_profile
                trainer_list.append({
                    'id': trainer.id,
                    'username': trainer.username,
                    'name': trainer_profile.name if trainer_profile.name else trainer.username,
                    'employee_id': trainer_profile.employee_id if trainer_profile.employee_id else None,
                    'department': trainer_profile.department if trainer_profile.department else None,
                })
            except TrainerProfile.DoesNotExist:
                trainer_list.append({
                    'id': trainer.id,
                    'username': trainer.username,
                    'name': trainer.username,
                    'employee_id': None,
                    'department': None,
                })
        
        data['trainers'] = trainer_list
        return Response(data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        trainer_id = serializer.validated_data.get('trainer_id')
        trainer = get_object_or_404(CustomUser, id=trainer_id, role='trainer')
        serializer.save(trainee=self.request.user, trainer=trainer)


class TraineeTaskSubmissionViewSet(viewsets_ViewSet):
    """
    GET    /trainee/trainee-tasks/               -> list (role-aware)
    POST   /trainee/trainee-tasks/               -> create (trainee/admin only)
    GET    /trainee/trainee-tasks/<pk>/          -> retrieve (role-aware)
    POST   /trainee/trainee-tasks/<pk>/review/   -> review (trainer/admin)
    """
    permission_classes = [permissions_IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None  # Disabled pagination

    # ---- helpers ----
    def _base_qs(self):
        # keep joins shallow; serializer can access reviewed_by.user safely
        return (TraineeTaskSubmission.objects
                .select_related("trainee", "reviewed_by")
                .all())

    def _trainer_profile(self, user):
        return getattr(user, "trainerprofile", None) or getattr(user, "trainer_profile", None)

    def _apply_admin_trainer_filters(self, qs):
        req = self.request
        status_q   = (req.query_params.get("status") or "").strip().lower()
        dept_q     = (req.query_params.get("department") or "").strip()
        trainee_q  = (req.query_params.get("trainee") or "").strip()
        reviewed_q = (req.query_params.get("reviewed_by") or "").strip()

        if status_q in ("submitted", "reviewed"):
            qs = qs.filter(status=status_q)
        if dept_q:
            qs = qs.filter(department__iexact=dept_q)
        if trainee_q:
            qs = qs.filter(trainee__username=trainee_q)
        if reviewed_q:
            qs = qs.filter(reviewed_by__user__username=reviewed_q)  # TrainerProfile -> User
        return qs

    # ---- list ----
    def list(self, request):
        # protect schema gen, if any tool still touches it
        if getattr(self, "swagger_fake_view", False):
            return Response([])

        user = request.user
        role = getattr(user, "role", None)

        if user.is_staff or getattr(user, "is_superuser", False):
            qs = self._apply_admin_trainer_filters(self._base_qs()).order_by("-submitted_at")

        elif role == "trainer":
            tp = self._trainer_profile(user)
            q = Q()
            if tp and getattr(tp, "department", None):
                q &= Q(department__iexact=str(tp.department))
            qs = self._apply_admin_trainer_filters(self._base_qs().filter(q)).order_by("-submitted_at")

        elif role == "trainee":
            qs = self._base_qs().filter(trainee_id=user.id).order_by("-submitted_at")
            status_q = (request.query_params.get("status") or "").strip().lower()
            if status_q in ("submitted", "reviewed"):
                qs = qs.filter(status=status_q)

        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        ser = TraineeTaskSubmissionSerializer(qs, many=True)
        return Response(ser.data)

    # ---- create (trainee/admin) ----
    @swagger_auto_schema(request_body=TraineeTaskSubmissionSerializer)
    def create(self, request):
        # Remove or comment out the fake_view check to allow real testing in Swagger after auth
        # if getattr(self, "swagger_fake_view", False):
        #     return Response(status=status.HTTP_201_CREATED)

        user = request.user
        role = getattr(user, "role", None)
        if role != "trainee" and not (user.is_staff or getattr(user, "is_superuser", False)):
            return Response({"error": "Only trainees can submit tasks."}, status=status.HTTP_403_FORBIDDEN)

        ser = TraineeTaskSubmissionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(trainee=user)
        return Response(TraineeTaskSubmissionSerializer(obj).data, status=status.HTTP_201_CREATED)

    # ---- retrieve ----
    def retrieve(self, request, pk=None):
        if getattr(self, "swagger_fake_view", False):
            return Response(status=status.HTTP_200_OK)

        user = request.user
        role = getattr(user, "role", None)

        try:
            obj = self._base_qs().get(pk=pk)
        except TraineeTaskSubmission.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        if user.is_staff or getattr(user, "is_superuser", False):
            pass
        elif role == "trainer":
            tp = self._trainer_profile(user)
            dept = getattr(tp, "department", None) if tp else None
            if not (dept and obj.department and str(dept).lower() == str(obj.department).lower()):
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        elif role == "trainee":
            if obj.trainee_id != user.id:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        return Response(TraineeTaskSubmissionSerializer(obj).data)

    # ---- review (trainer/admin) ----
    @action(detail=True, methods=["post"], url_path="review", parser_classes=[MultiPartParser, FormParser])
    def review(self, request, pk=None):
        if getattr(self, "swagger_fake_view", False):
            return Response(status=status.HTTP_200_OK)

        user = request.user
        is_admin = user.is_staff or getattr(user, "is_superuser", False)
        is_trainer = getattr(user, "role", None) == "trainer"
        if not (is_admin or is_trainer):
            return Response({"error": "Only trainers or admins can review submissions."},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            obj = self._base_qs().get(pk=pk)
        except TraineeTaskSubmission.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        tp = self._trainer_profile(user)
        if is_trainer and tp:
            dept = getattr(tp, "department", None)
            if obj.department and dept and str(obj.department).lower() != str(dept).lower():
                return Response({"error": "You can only review submissions from your department."},
                                status=status.HTTP_403_FORBIDDEN)

        ser = TraineeTaskReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        for f, v in ser.validated_data.items():
            setattr(obj, f, v)

        obj.status = TraineeTaskSubmission.STATUS_REVIEWED
        obj.reviewed_by = tp if (is_trainer and tp) else None
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=[
            "marks", "feedback", "review_file",
            "status", "reviewed_by", "reviewed_at", "updated_at"
        ])
        return Response(TraineeTaskSubmissionSerializer(obj).data, status=status.HTTP_200_OK)
    
class BannerViewSet(viewsets.ModelViewSet):
    """
    Endpoints:
    - GET    /api/banners/           -> list
    - POST   /api/banners/           -> create (multipart)
    - GET    /api/banners/{id}/      -> retrieve
    - PUT    /api/banners/{id}/      -> update
    - PATCH  /api/banners/{id}/      -> partial update
    - DELETE /api/banners/{id}/      -> delete
    """
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer
    permission_classes = [permissions.AllowAny]  # adjust as needed
    parser_classes = [MultiPartParser, FormParser]  # to accept image uploads


class IsAuth(permissions.IsAuthenticated):
    pass

class ConcernViewSet(viewsets.ViewSet):
    """
    GET    /concerns/                     -> list (role-aware)
    POST   /concerns/                     -> create (trainee/employee/admin/trainer)
    GET    /concerns/<pk>/                -> retrieve (role-aware)
    PATCH  /concerns/<pk>/status/         -> change status (trainer/admin/assignee)
    PATCH  /concerns/<pk>/assign/         -> assign to user by username (trainer/admin)
    POST   /concerns/<pk>/comment/        -> add comment (participants + trainer/admin)
    """
    permission_classes = [IsAuth]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    # helpers
    def _base_qs(self):
        return Concern.objects.select_related("created_by", "assigned_to")

    def _trainer_profile(self, user):
        return getattr(user, "trainerprofile", None) or getattr(user, "trainer_profile", None)

    def _apply_filters(self, qs):
        p = self.request.query_params
        status_q   = (p.get("status") or "").strip().lower()
        prio_q     = (p.get("priority") or "").strip().lower()
        dept_q     = (p.get("department") or "").strip()
        assignee_q = (p.get("assignee") or "").strip()
        creator_q  = (p.get("creator") or "").strip()
        category_q = (p.get("category") or "").strip()

        if status_q in dict(Concern.STATUS_CHOICES):
            qs = qs.filter(status=status_q)
        if prio_q in dict(Concern.PRIORITY_CHOICES):
            qs = qs.filter(priority=prio_q)
        if dept_q:
            qs = qs.filter(department__iexact=dept_q)
        if assignee_q:
            qs = qs.filter(assigned_to__username=assignee_q)
        if creator_q:
            qs = qs.filter(created_by__username=creator_q)
        if category_q:
            qs = qs.filter(category__iexact=category_q)
        return qs

    # list
    def list(self, request):
        user = request.user
        role = getattr(user, "role", None)

        if user.is_staff or getattr(user, "is_superuser", False):
            qs = self._apply_filters(self._base_qs()).order_by("-created_at")
        elif role == "trainer":
            tp = self._trainer_profile(user)
            q = Q(assigned_to=user) | Q(department__iexact=getattr(tp, "department", "")) | Q(is_private=False)
            qs = self._apply_filters(self._base_qs().filter(q)).order_by("-created_at")
        else:  # trainee/employee
            q = Q(created_by=user) | Q(assigned_to=user) | Q(is_private=False, department__iexact=getattr(user, "department", ""))
            qs = self._apply_filters(self._base_qs().filter(q)).order_by("-created_at")

        return Response(ConcernListSerializer(qs, many=True).data)

    # create
    def create(self, request):
        ser = ConcernCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(ConcernDetailSerializer(obj).data, status=status.HTTP_201_CREATED)

    # retrieve
    def retrieve(self, request, pk=None):
        try:
            obj = self._base_qs().get(pk=pk)
        except Concern.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        user = request.user
        if user.is_staff or getattr(user, "is_superuser", False):
            pass
        elif obj.is_private:
            # Only creator, assignee, relevant trainer dept can view private concerns
            allowed = {obj.created_by_id, getattr(obj.assigned_to, "id", None)}
            if user.id not in allowed:
                tp = self._trainer_profile(user)
                if not (tp and obj.department and str(tp.department).lower() == str(obj.department).lower()):
                    return Response({"error": "Unauthorized"}, status=403)
        # public concerns are visible by dept (already covered in list)
        return Response(ConcernDetailSerializer(obj).data)

    # change status
    @action(detail=True, methods=["patch"], url_path="status")
    def change_status(self, request, pk=None):
        try:
            obj = Concern.objects.get(pk=pk)
        except Concern.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        user = request.user
        is_admin = user.is_staff or getattr(user, "is_superuser", False)
        is_handler = obj.assigned_to_id == user.id
        is_trainer = getattr(user, "role", None) == "trainer"
        if not (is_admin or is_handler or is_trainer):
            return Response({"error": "Unauthorized"}, status=403)

        ser = ConcernStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj.status = ser.validated_data["status"]
        obj.save(update_fields=["status", "updated_at"])
        return Response(ConcernDetailSerializer(obj).data)

    # assign to user (by username)
    @action(detail=True, methods=["patch"], url_path="assign")
    def assign(self, request, pk=None):
        try:
            obj = Concern.objects.get(pk=pk)
        except Concern.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        user = request.user
        if not (user.is_staff or getattr(user, "is_superuser", False) or getattr(user, "role", None) == "trainer"):
            return Response({"error": "Only trainers/admins can assign concerns."}, status=403)

        ser = ConcernAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj.assigned_to = ser.validated_data["assigned_to"]
        obj.status = Concern.ST_INPROGRESS
        obj.save(update_fields=["assigned_to", "status", "updated_at"])
        return Response(ConcernDetailSerializer(obj).data)

    # comment
    @action(detail=True, methods=["post"], url_path="comment", parser_classes=[MultiPartParser, FormParser])
    def comment(self, request, pk=None):
        try:
            obj = Concern.objects.get(pk=pk)
        except Concern.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        # Only creator, assignee, trainers/admin may comment
        user = request.user
        is_admin = user.is_staff or getattr(user, "is_superuser", False)
        is_trainer = getattr(user, "role", None) == "trainer"
        if not (is_admin or is_trainer or user.id in (obj.created_by_id, getattr(obj.assigned_to, "id", None))):
            return Response({"error": "Unauthorized"}, status=403)

        ser = ConcernCommentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        c = ConcernComment.objects.create(concern=obj, author=user, **ser.validated_data)
        return Response(ConcernCommentSerializer(c).data, status=201)