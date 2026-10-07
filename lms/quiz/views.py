from django.shortcuts import render
from rest_framework.generics import ListAPIView,RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import QuizSerializer
from .models import Quiz,Question,Answer,Result,ResultAnswer,normalize_answer
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
        questions = []
        for q in quiz.get_questions():
            answers = q.get_answers()
            question_data.append({str(q): [a.answer for a in answers]})
            questions.append({
                'id': q.id,
                'question_number': q.question_number,
                'question': q.question,
                'question_image': request.build_absolute_uri(q.question_image.url) if q.question_image else None,
                'allow_custom_answer': q.custom_answer_enabled,
                'answers': [
                    {
                        'id': a.id,
                        'answer': a.answer,
                        'answer_image': a.image_url(request),
                    }
                    for a in answers
                ],
            })

        return Response({'data': question_data, 'questions': questions, 'time': quiz.time})


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

        # New format: {"answers": [{"question_id": 5, "answer_id": 12}, {"question_id": 6, "custom_answer": "text"}, ...]}
        # Old format: {"<question text>": "<answer text>", ...}
        if isinstance(data.get("answers"), list):
            submitted = [
                (item.get("question_id"), item.get("answer_id"), True, str(item.get("custom_answer") or "").strip())
                for item in data["answers"] if isinstance(item, dict)
            ]
        else:
            submitted = [(q, a, False, "") for q, a in data.items()]

        for question_key, answer_selected, by_id, custom_answer in submitted:
            if by_id:
                question = Question.objects.filter(pk=question_key, quiz=quiz).first()
            else:
                question = Question.objects.filter(question=question_key, quiz=quiz).first()
            if not question:
                continue  # Skip invalid question

            correct_answer_obj = Answer.objects.filter(question=question, correct=True).first()
            correct_answer_text = (correct_answer_obj.answer if correct_answer_obj else "") or question.expected_answer or "N/A"

            selected_answer_obj = None
            selected_answer_text = None
            is_correct = False

            if not question.custom_answer_enabled:
                custom_answer = ""

            if custom_answer and not answer_selected:
                # Written answer: correct if it matches the expected answer or the correct option's text,
                # otherwise saved as wrong and can be reviewed in admin (Result answers)
                selected_answer_text = custom_answer
                if question.matches_typed_answer(custom_answer):
                    is_correct = True
                    score += 1
                    correct_questions += 1
                else:
                    wrong_questions += 1
            elif answer_selected:
                if by_id:
                    selected_answer_obj = Answer.objects.filter(question=question, pk=answer_selected).first()
                else:
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
                custom_answer=custom_answer if not selected_answer_obj else "",
                is_correct=is_correct
            )

            # Store feedback
            questions_feedback.append({
                "question_id": question.id,
                "question": question.question,
                "question_image": request.build_absolute_uri(question.question_image.url) if question.question_image else None,
                "correct_answer": correct_answer_text,
                "correct_answer_image": correct_answer_obj.image_url(request) if correct_answer_obj else None,
                "student_answer": selected_answer_text,
                "student_answer_image": selected_answer_obj.image_url(request) if selected_answer_obj else None,
                "is_custom_answer": bool(custom_answer and not selected_answer_obj),
                "is_correct": is_correct
            })

        # Step 3: Finalize result
        final_score = round(score * multiplier, 2)
        result.score = final_score
        result.correct_questions = correct_questions
        result.wrong_questions = wrong_questions
        result.unattempted_questions = unattempted_questions
        result.save()

        # Step 4: Certificate (generation disabled for now)
        passed = final_score >= quiz.passing_score_percentage
        # certificate_file = generate_certificate(user, quiz, final_score, passed, result.date_attempted)
        # result.certificate.save(certificate_file.name, certificate_file)

        # Step 5: Return full response
        return Response({
            "passed": passed,
            "score": f"{final_score:.2f}",
            "correct_questions": correct_questions,
            "wrong_questions": wrong_questions,
            "unattempted_questions": unattempted_questions,
            "questions_feedback": questions_feedback
        })


def can_review_answers(user):
    return user.is_superuser or getattr(user, "role", "") in ("admin", "trainer")


def can_review_result(user, result):
    """Admins can review any attempt; trainers only attempts from their assigned departments."""
    if user.is_superuser or getattr(user, "role", "") == "admin":
        return True
    if getattr(user, "role", "") != "trainer":
        return False
    from user.models import TrainerProfile
    from user.TrainerView import get_trainer_allowed_departments  # imported here to avoid a circular import
    trainer = TrainerProfile.objects.filter(user=user).first()
    if not trainer:
        return False
    student = (TraineeProfile.objects.filter(user=result.user).first()
               or EmployeeProfile.objects.filter(user=result.user).first())
    department = student.department if student else result.quiz.department
    return department in get_trainer_allowed_departments(trainer)


class QuizAttemptDetailAPIView(APIView):
    """All questions of a quiz with one user's submitted answers, for admins/trainers to review."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, username):
        if not can_review_answers(request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        result = (Result.objects.filter(quiz_id=pk, user__username__iexact=username)
                  .select_related("quiz", "user").order_by("-date_attempted").first())
        if not result:
            raise NotFound("This user has not attempted this quiz.")
        if not can_review_result(request.user, result):
            return Response({"detail": "This trainee is not in your departments."}, status=status.HTTP_403_FORBIDDEN)

        submitted = {ra.question_id: ra for ra in result.resultanswer_set.select_related("selected_answer")}
        image = lambda f: request.build_absolute_uri(f.url) if f else None

        questions = []
        for q in result.quiz.question_set.order_by("question_number", "id").prefetch_related("answer_set"):
            options = list(q.answer_set.all())
            correct = next((a for a in options if a.correct), None)
            ra = submitted.get(q.id)
            questions.append({
                "question_id": q.id,
                "question_number": q.question_number,
                "question": q.question,
                "question_image": image(q.question_image),
                "options": [
                    {"id": a.id, "answer": a.answer, "answer_image": image(a.answer_image), "correct": a.correct}
                    for a in options
                ],
                "correct_answer": (correct.answer if correct else "") or q.expected_answer or None,
                "correct_answer_image": image(correct.answer_image) if correct else None,
                # Submitted answer (all None if the user skipped the question)
                "result_answer_id": ra.id if ra else None,
                "selected_answer_id": ra.selected_answer_id if ra else None,
                "selected_answer": ra.selected_answer.answer if ra and ra.selected_answer else None,
                "custom_answer": (ra.custom_answer or None) if ra else None,
                "is_correct": ra.is_correct if ra else False,
            })

        profile = (TraineeProfile.objects.filter(user=result.user).first()
                   or EmployeeProfile.objects.filter(user=result.user).first())

        return Response({
            "result_id": result.id,
            "quiz_id": result.quiz_id,
            "quiz_name": result.quiz.quiz_name,
            "passing_score_percentage": result.quiz.passing_score_percentage,
            "username": result.user.username,
            "name": (profile.name if profile else "") or result.user.get_full_name() or result.user.username,
            "score": round(result.score, 2),
            "correct_questions": result.correct_questions,
            "wrong_questions": result.wrong_questions,
            "unattempted_questions": result.unattempted_questions,
            "date_attempted": result.date_attempted,
            "questions": questions,
        })


class ResultAnswerMarkAPIView(APIView):
    """Mark one submitted answer correct/incorrect; the result's score is recalculated."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not can_review_answers(request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if not isinstance(request.data.get("is_correct"), bool):
            return Response({"detail": "is_correct must be true or false."}, status=status.HTTP_400_BAD_REQUEST)

        ra = ResultAnswer.objects.select_related("result__quiz").filter(pk=pk).first()
        if not ra:
            raise NotFound("Answer not found.")
        if not can_review_result(request.user, ra.result):
            return Response({"detail": "This trainee is not in your departments."}, status=status.HTTP_403_FORBIDDEN)
        if not ra.selected_answer_id and not ra.custom_answer:
            return Response({"detail": "This question was not answered."}, status=status.HTTP_400_BAD_REQUEST)
        ra.is_correct = request.data["is_correct"]
        ra.save(update_fields=["is_correct"])
        result = ra.result
        result.recalculate()

        return Response({
            "result_answer_id": ra.id,
            "is_correct": ra.is_correct,
            "score": round(result.score, 2),
            "correct_questions": result.correct_questions,
            "wrong_questions": result.wrong_questions,
        })
