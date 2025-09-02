from django.shortcuts import render
from rest_framework.generics import ListAPIView,RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import QuizSerializer
from .models import Quiz,Question,Answer,Result,ResultAnswer
from user.models import TraineeProfile,EmployeeProfile
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from .utils import generate_certificate
from django.db.models import Q


class QuizListAPIView(ListAPIView):
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated]  # any logged-in user: employee/trainee/trainer

    def get_queryset(self):
        qs = Quiz.objects.all()

        # Optional filters
        department = (self.request.query_params.get("department") or "").strip()
        quiz_type  = (self.request.query_params.get("quiz_type") or "").strip()
        search     = (self.request.query_params.get("search") or "").strip()
        ordering   = (self.request.query_params.get("ordering") or "-id").strip()

        if department:
            qs = qs.filter(department=department)

        if quiz_type:
            qs = qs.filter(quiz_type=quiz_type)

        if search:
            qs = qs.filter(
                Q(quiz_name__icontains=search) |
                Q(topic__icontains=search)
            )

        # Allow a few safe ordering fields; default to most recent
        if ordering not in {"id", "-id", "quiz_name", "-quiz_name"}:
            ordering = "-id"

        return qs.order_by(ordering)


class QuizDetailAPIView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    lookup_field = 'pk'
    
class QuizDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        quiz = Quiz.objects.get(pk=pk)
        question_data = []
        for q in quiz.get_questions():
            answers = [a.answer for a in q.get_answers()]
            question_data.append({str(q): answers})
        
        return Response({'data': question_data, 'time': quiz.time}) 


@method_decorator(csrf_exempt, name='dispatch')
class QuizResultAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from quiz.models import ResultAnswer

        data = request.data
        user = request.user
        quiz = Quiz.objects.get(pk=pk)

        if Result.objects.filter(user=user, quiz=quiz).exists():
            return Response({
                "message": "You have already attempted this quiz. Only one attempt is allowed."
            }, status=status.HTTP_403_FORBIDDEN)

        total_questions = quiz.no_of_questions
        score = 0
        correct_questions = 0
        wrong_questions = 0
        unattempted_questions = 0
        multiplier = 100 / total_questions

        # Step 1: Create Result early
        result = Result.objects.create(
            quiz=quiz,
            user=user,
            score=0,
            correct_questions=0,
            wrong_questions=0,
            unattempted_questions=0
        )

        # Step 2: Track feedback list
        questions_feedback = []

        for question_text, answer_selected in data.items():
            try:
                question = Question.objects.get(question=question_text, quiz=quiz)
            except Question.MultipleObjectsReturned:
                question = Question.objects.filter(question=question_text, quiz=quiz).first()
            except Question.DoesNotExist:
                continue  # Skip invalid question

            correct_answer_obj = Answer.objects.filter(question=question, correct=True).first()
            correct_answer_text = correct_answer_obj.answer if correct_answer_obj else "N/A"

            selected_answer_obj = None
            selected_answer_text = None
            is_correct = False

            if answer_selected:
                selected_answer_obj = Answer.objects.filter(question=question, answer=answer_selected).first()
                if selected_answer_obj:
                    selected_answer_text = selected_answer_obj.answer
                    if selected_answer_obj.correct:
                        is_correct = True
                        score += 1
                        correct_questions += 1
                    else:
                        wrong_questions += 1
                else:
                    wrong_questions += 1  # answer doesn't match any option
            else:
                unattempted_questions += 1

            # Save ResultAnswer
            ResultAnswer.objects.create(
                result=result,
                question=question,
                selected_answer=selected_answer_obj,
                is_correct=is_correct
            )

            # Store feedback
            questions_feedback.append({
                "question": question.question,
                "correct_answer": correct_answer_text,
                "student_answer": selected_answer_text,
                "is_correct": is_correct
            })

        # Step 3: Finalize result
        final_score = round(score * multiplier, 2)
        result.score = final_score
        result.correct_questions = correct_questions
        result.wrong_questions = wrong_questions
        result.unattempted_questions = unattempted_questions
        result.save()

        # Step 4: Certificate
        passed = final_score >= quiz.passing_score_percentage
        certificate_file = generate_certificate(user, quiz, final_score, passed, result.date_attempted)
        result.certificate.save(certificate_file.name, certificate_file)

        # Step 5: Return full response
        return Response({
            "passed": passed,
            "score": f"{final_score:.2f}",
            "correct_questions": correct_questions,
            "wrong_questions": wrong_questions,
            "unattempted_questions": unattempted_questions,
            "questions_feedback": questions_feedback
        })
