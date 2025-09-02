from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    SubjectSerializer, TraineeSerializer,EmployeeSerializer, LessonSerializer,QueryResponseSerializer, QuerySerializer,ContentEndSerializer,
    ContentStartSerializer,MacroplannerSerializer,MicroplannerSerializer,UserLoginActivitySerializer,NotificationReceiptSerializer,
    ActiveQuizListSerializer
)
from .models import (
    Subject,TraineeProfile, UserLoginActivity,Query,Macroplanner, Microplanner,CustomUser,AssessmentReport,EmployeeProfile,NotificationReceipt,
    Lesson,EmployeeLessonCompletion,TraineeLessonCompletion
)
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema # type: ignore
from rest_framework.generics import ListAPIView
from django.utils.timezone import now
from quiz.models import Result, Quiz,Answer,ResultAnswer
from quiz.serializers import QuizSerializer
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser, FormParser
from collections import defaultdict
from datetime import timedelta
from django.db.models import Count,Avg,Max
from django.db.models import Exists, OuterRef
from django.utils import timezone


class EmployeeDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_user_department(self, user):
        """Helper method to get user's department from EmployeeProfile or TraineeProfile."""
        try:
            return EmployeeProfile.objects.only("department").get(user=user).department
        except EmployeeProfile.DoesNotExist:
            try:
                return TraineeProfile.objects.only("department").get(user=user).department
            except TraineeProfile.DoesNotExist:
                return None

    def get_employee_reports(self, student, quiz_type):
        """Generate quiz reports for the employee."""
        results = Result.objects.filter(user=student.user, quiz__quiz_type=quiz_type)
        quiz_ids = results.values_list("quiz_id", flat=True)

        reports = AssessmentReport.objects.filter(
            quiz__id__in=quiz_ids,
            quiz__quiz_type=quiz_type
        )

        report_list = []
        for report in reports:
            quiz = report.quiz
            employee_result = results.filter(quiz=quiz).order_by('-date_attempted').first()
            if not employee_result:
                continue

            total_questions = quiz.no_of_questions
            correct_questions = getattr(employee_result, 'correct_questions', 0)
            wrong_questions = getattr(employee_result, 'wrong_questions', 0)
            unattempted_questions = getattr(employee_result, 'unattempted_questions', 0)
            employee_score = employee_result.score

            avg_score = Result.objects.filter(quiz=quiz).aggregate(avg=Avg('score'))['avg'] or 0
            highest_score = Result.objects.filter(quiz=quiz).aggregate(highest=Max('score'))['highest'] or 0

            feedback = []
            answers = ResultAnswer.objects.filter(result=employee_result).select_related('question', 'selected_answer')
            for ans in answers:
                correct_answer_obj = Answer.objects.filter(question=ans.question, correct=True).first()
                correct_answer_text = correct_answer_obj.answer if correct_answer_obj else "N/A"
                selected_answer_text = ans.selected_answer.answer if ans.selected_answer else None
                feedback.append({
                    "question": ans.question.question,
                    "correct_answer": correct_answer_text,
                    "employee_answer": selected_answer_text,
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
                "employee_score": round(employee_score, 2),
                "average_score": round(avg_score, 2),
                "highest_score": round(highest_score, 2),
                "certificate_url": employee_result.certificate.url if employee_result.certificate else None,
                "questions_feedback": feedback
            })

        return report_list

    def get(self, request, username):
        try:
            user = get_object_or_404(CustomUser, username=username)
            if request.user != user:
                return Response({"error": "Unauthorized access."}, status=status.HTTP_403_FORBIDDEN)

            # Determine profile type and fetch object
            try:
                employee_obj = get_object_or_404(EmployeeProfile, user=user)
                profile_data = EmployeeSerializer(employee_obj).data  # Use EmployeeSerializer
            except EmployeeProfile.DoesNotExist:
                try:
                    employee_obj = get_object_or_404(TraineeProfile, user=user)
                    profile_data = TraineeSerializer(employee_obj).data  # Use TraineeSerializer
                except TraineeProfile.DoesNotExist:
                    return Response(
                        {"error": "No employee or trainee profile found for this user."},
                        status=status.HTTP_404_NOT_FOUND
                    )

            department = self._get_user_department(user)
            if department is None:
                return Response(
                    {"error": "No department associated with this user."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Determine if user is trainee
            is_trainee = TraineeProfile.objects.filter(user=user).exists()

            # Subjects (filtered for frontend, department)
            subjects_qs = Subject.objects.filter(
                department=department,
                display_on_frontend=True
            ).order_by("name")
            subjects_count = subjects_qs.count()
            subjects_data = SubjectSerializer(subjects_qs, many=True, context={"request": request}).data

            # New subjects (based on is_new field)
            new_subjects_qs = subjects_qs.filter(is_new=True)
            new_subjects_data = SubjectSerializer(new_subjects_qs, many=True, context={"request": request}).data

            # New lessons (across all subjects in department, based on is_new)
            new_lessons_qs = Lesson.objects.filter(
                department=department,
                display_on_frontend=True,
                is_new=True
            ).order_by("subject__name", "position")
            new_lessons_data = LessonSerializer(new_lessons_qs, many=True, context={"request": request}).data

            # Lesson completion tracking
            completions = EmployeeLessonCompletion.objects.filter(
                employee=employee_obj,
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

            # For non-trainees (employees), optionally limit subjects to new ones
            if not is_trainee:
                subjects_data = new_subjects_data
                subjects_count = len(subjects_data)

            # Active quizzes
            quizzes = Quiz.objects.filter(
                department=department,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            )
            quiz_serializer = QuizSerializer(quizzes, many=True)

            # Login count
            login_count = UserLoginActivity.objects.filter(login_username=user).count()

            # Quiz reports
            homework_reports = self.get_employee_reports(employee_obj, "homework")
            pre_assessment_reports = self.get_employee_reports(employee_obj, "pre-assessment")
            post_assessment_reports = self.get_employee_reports(employee_obj, "post-assessment")
            daily_quiz_reports = self.get_employee_reports(employee_obj, "daily-quiz")
            weekly_quiz_reports = self.get_employee_reports(employee_obj, "weekly-quiz")
            monthly_quiz_reports = self.get_employee_reports(employee_obj, "monthly-quiz")
            final_exam_reports = self.get_employee_reports(employee_obj, "final_exam")

            # Active homework
            active_homework = QuizSerializer(
                Quiz.objects.filter(
                    department=department,
                    start_date__lte=timezone.now(),
                    end_date__gte=timezone.now()
                ),
                many=True
            ).data

            # Active quizzes with attempt status
            attempted_subq = Result.objects.filter(user=user, quiz=OuterRef("pk"))
            active_quizzes_qs = (
                Quiz.objects
                .filter(
                    department=department,
                    start_date__lte=timezone.now(),
                    end_date__gte=timezone.now()
                )
                .annotate(has_attempted=Exists(attempted_subq))
                .order_by("-start_date")
            )
            active_quizzes_data = ActiveQuizListSerializer(active_quizzes_qs, many=True).data

            response_data = {
                "profile": profile_data,
                "is_trainee": is_trainee,
                "subjects": subjects_data,
                "subjects_count": subjects_count,
                "new_subjects": new_subjects_data,
                "new_subjects_count": len(new_subjects_data),
                "new_lessons": new_lessons_data,
                "new_lessons_count": len(new_lessons_data),
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
                "active_homework": active_homework,
                "completed_lessons_count": completed_lessons_count,
                "completed_lesson_ids": completed_lesson_ids,
                "completed_per_subject": completed_per_subject_data
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except EmployeeProfile.DoesNotExist:
            return Response({"error": "Employee profile does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        
class EmployeeAvailableQuizListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuizSerializer

    def get_queryset(self):
        user = self.request.user

        try:
            employee = EmployeeProfile.objects.get(user=user)
        except EmployeeProfile.DoesNotExist:
            raise NotFound('Employee profile not found.')

        attempted_quiz_ids = Result.objects.filter(user=user).values_list("quiz_id", flat=True)

        quizzes = Quiz.objects.filter(
            department=employee.department,
            start_date__lte=now(),
            end_date__gte=now()
        ).exclude(id__in=attempted_quiz_ids)

        return quizzes
    
class EmployeeQueryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            employee_profile = get_object_or_404(EmployeeProfile, user=request.user)

            queries = Query.objects.filter(raised_by=request.user)
            serializer = QuerySerializer(queries, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except EmployeeProfile.DoesNotExist:
            return Response({"error": "No EmployeeProfile matches the given query."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class EmployeeQueryCreateAPIView(APIView):
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

class EmployeeQueryResponseAPIView(APIView):
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
    

class EmployeeMacroplannerListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Ensure the requester has a TraineeProfile
        try:
            employee = EmployeeProfile.objects.select_related("user").get(user=request.user)
        except TraineeProfile.DoesNotExist:
            return Response(
                {"detail": "Employee profile not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Fetch macroplanners for employee's department
        qs = (
            Macroplanner.objects
            .filter(department=employee.department)
            .order_by("-id")  # change to "-created_at" if you have that field
        )

        serializer = MacroplannerSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class EmployeeMicroplannerListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Ensure the requester has a TraineeProfile
        try:
            trainee = EmployeeProfile.objects.select_related("user").get(user=request.user)
        except EmployeeProfile.DoesNotExist:
            return Response(
                {"detail": "Employee profile not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Fetch microplanners for trainee's department
        qs = (
            Microplanner.objects
            .filter(department=trainee.department)
            .order_by("-id")  # or "-created_at" if available
        )

        serializer = MicroplannerSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class EmployeeLoginActivityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            employee_profile = EmployeeProfile.objects.get(user=user)
        except EmployeeProfile.DoesNotExist:
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
            "employee_profile": {
                "name": employee_profile.name,
                "department": employee_profile.department,
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


class EmployeeNotificationsView(BaseUserNotificationsView):
    def list(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'employee':
            return Response({"error": "Not an employee."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)
    
class MarkLessonCompletedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_slug):
        try:
            user = request.user
            lesson = get_object_or_404(Lesson, slug=lesson_slug)

            # Determine the user's role using the role field
            role = user.role.lower()
            if role == 'trainee':
                try:
                    profile = user.trainee_profile
                    completion_model = TraineeLessonCompletion
                    completion_field = 'trainee'
                except TraineeProfile.DoesNotExist:
                    return Response({"error": "Trainee profile not found."}, status=status.HTTP_400_BAD_REQUEST)
            elif role == 'employee':
                try:
                    profile = user.employee_profile
                    completion_model = EmployeeLessonCompletion
                    completion_field = 'employee'
                except EmployeeProfile.DoesNotExist:
                    return Response({"error": "Employee profile not found."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"error": "Only trainees and employees can mark lessons as completed."}, status=status.HTTP_403_FORBIDDEN)

            # Check department compatibility (optional, adjust based on your models)
            if hasattr(lesson, 'department') and hasattr(profile, 'department'):
                if lesson.department != profile.department:
                    return Response({"error": "Lesson not available for your department."}, status=status.HTTP_403_FORBIDDEN)

            # Check if the lesson is already completed
            completion, created = completion_model.objects.get_or_create(
                **{completion_field: profile, 'lesson': lesson},
                defaults={'completed': True, 'completed_at': timezone.now()}
            )
            if not created and not completion.completed:
                completion.completed = True
                completion.completed_at = timezone.now()
                completion.save()
            elif created or completion.completed:
                return Response({"message": "Lesson already marked as completed.", "completed_at": completion.completed_at}, status=status.HTTP_200_OK)

            return Response({"message": "Lesson marked as completed.", "completed_at": timezone.now()}, status=status.HTTP_200_OK)

        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)