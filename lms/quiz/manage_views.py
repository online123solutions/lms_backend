"""
Quiz management API for the admin dashboard (create/edit/delete quizzes, questions and options).

Questions are saved together with their options in one multipart request:
  question fields + question_image (file) + remove_question_image ("true")
  answers: JSON list [{"id"?, "answer", "correct", "image_field"?, "remove_image"?}, ...]
           where image_field names a file in the same request (e.g. "answer_image_0").
"""
import json

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from .models import Answer, Department, Question, Quiz


class IsQuizAdmin(BasePermission):
    message = "Only admins can manage quizzes."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, "role", "") == "admin"))


def _image_url(request, f):
    return request.build_absolute_uri(f.url) if f else None


class QuizManageSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True)
    attempts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id", "quiz_name", "topic", "department", "quiz_type", "no_of_questions", "time",
            "passing_score_percentage", "date", "start_date", "end_date",
            "question_count", "attempts_count",
        ]
        read_only_fields = ["no_of_questions", "date"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_date": "End must be after the start."})
        for field, low, high in (("time", 1, 1440), ("passing_score_percentage", 0, 100)):
            if field in attrs and not (low <= attrs[field] <= high):
                raise serializers.ValidationError({field: f"Must be between {low} and {high}."})
        return attrs


def sync_question_count(quiz):
    """Scores are computed against no_of_questions, so keep it equal to the real number of questions."""
    quiz.no_of_questions = quiz.question_set.count()
    quiz.save(update_fields=["no_of_questions"])


class QuizManageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsQuizAdmin]
    serializer_class = QuizManageSerializer

    def get_queryset(self):
        qs = Quiz.objects.annotate(
            question_count=Count("question", distinct=True),
            attempts_count=Count("result", distinct=True),
        ).order_by("-id")
        p = self.request.query_params
        if p.get("department"):
            qs = qs.filter(department=p["department"])
        if p.get("quiz_type"):
            qs = qs.filter(quiz_type=p["quiz_type"])
        if p.get("search"):
            qs = qs.filter(Q(quiz_name__icontains=p["search"]) | Q(topic__icontains=p["search"]))
        return qs

    def perform_create(self, serializer):
        from django.utils import timezone
        serializer.save(created_by=self.request.user, date=timezone.now(), no_of_questions=0)

    def destroy(self, request, *args, **kwargs):
        quiz = self.get_object()
        attempts = quiz.result_set.count()
        if attempts and request.query_params.get("force") != "true":
            return Response(
                {"detail": f"This quiz has {attempts} attempt(s). Deleting it also deletes their results.",
                 "attempts_count": attempts},
                status=status.HTTP_409_CONFLICT,
            )
        quiz.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def options(self, request):
        """Choices for the quiz form."""
        return Response({
            "departments": [{"value": v, "label": l} for v, l in Department],
            "quiz_types": [{"value": v, "label": l} for v, l in Quiz.QUIZ_TYPE_CHOICES],
        })


def serialize_question(request, q):
    return {
        "id": q.id,
        "quiz": q.quiz_id,
        "question_number": q.question_number,
        "question": q.question,
        "question_image": _image_url(request, q.question_image),
        "allow_custom_answer": q.allow_custom_answer,
        "expected_answer": q.expected_answer,
        "answers": [
            {"id": a.id, "answer": a.answer, "answer_image": _image_url(request, a.answer_image), "correct": a.correct}
            for a in q.answer_set.all().order_by("id")
        ],
    }


def _truthy(value):
    return str(value).lower() in ("1", "true", "on", "yes")


class QuestionManageViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsQuizAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def list(self, request):
        quiz_id = request.query_params.get("quiz")
        if not quiz_id:
            return Response({"detail": "quiz is required."}, status=status.HTTP_400_BAD_REQUEST)
        questions = (Question.objects.filter(quiz_id=quiz_id)
                     .prefetch_related("answer_set").order_by("question_number", "id"))
        return Response([serialize_question(request, q) for q in questions])

    def create(self, request):
        return self._save(request, Question())

    def partial_update(self, request, pk=None):
        question = Question.objects.filter(pk=pk).first()
        if not question:
            return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)
        return self._save(request, question)

    update = partial_update

    def destroy(self, request, pk=None):
        question = Question.objects.filter(pk=pk).select_related("quiz").first()
        if not question:
            return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)
        quiz = question.quiz
        question.delete()
        sync_question_count(quiz)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _save(self, request, question):
        data, files = request.data, request.FILES
        errors = {}

        if question.pk is None:
            quiz = Quiz.objects.filter(pk=data.get("quiz")).first()
            if not quiz:
                return Response({"quiz": ["Choose a quiz."]}, status=status.HTTP_400_BAD_REQUEST)
            question.quiz = quiz

        if "question_number" in data:
            try:
                question.question_number = int(data["question_number"])
            except (TypeError, ValueError):
                errors["question_number"] = ["Enter a number."]
        elif question.pk is None:
            last = question.quiz.question_set.order_by("-question_number").first()
            question.question_number = (last.question_number + 1) if last else 1

        if "question" in data:
            question.question = (data.get("question") or "").strip()[:500]
        if "allow_custom_answer" in data:
            question.allow_custom_answer = _truthy(data["allow_custom_answer"])
        if "expected_answer" in data:
            question.expected_answer = (data.get("expected_answer") or "").strip()[:500]
        if "question_image" in files:
            question.question_image = files["question_image"]
        elif _truthy(data.get("remove_question_image", "")):
            question.question_image = None

        if not question.question and not question.question_image:
            errors["question"] = ["Enter the question text or upload an image."]

        # Options
        try:
            raw = data.get("answers", "[]")
            answers = json.loads(raw) if isinstance(raw, str) else (raw or [])
            if not isinstance(answers, list):
                raise ValueError
        except ValueError:
            return Response({"answers": ["Invalid answers data."]}, status=status.HTTP_400_BAD_REQUEST)

        existing = {a.id: a for a in question.answer_set.all()} if question.pk else {}
        cleaned = []
        for i, item in enumerate(answers):
            if not isinstance(item, dict):
                continue
            ans = existing.get(item.get("id")) or Answer()
            ans.answer = (item.get("answer") or "").strip()[:500]
            ans.correct = bool(item.get("correct"))
            image_field = item.get("image_field")
            if image_field and image_field in files:
                ans.answer_image = files[image_field]
            elif item.get("remove_image"):
                ans.answer_image = None
            if not ans.answer and not ans.answer_image:
                errors.setdefault("answers", []).append(f"Option {i + 1}: enter text or upload an image.")
            cleaned.append(ans)

        if cleaned and not any(a.correct for a in cleaned) and not question.expected_answer and not question.allow_custom_answer:
            errors.setdefault("answers", []).append(
                "Mark the correct option (or allow written answers so they can be reviewed)."
            )
        if not cleaned and not question.expected_answer:
            # Written-only question without an expected answer: allowed, answers are reviewed manually
            question.allow_custom_answer = True

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        created = question.pk is None
        with transaction.atomic():
            question.save()
            keep_ids = []
            for ans in cleaned:
                ans.question = question
                ans.save()
                keep_ids.append(ans.id)
            question.answer_set.exclude(id__in=keep_ids).delete()
            sync_question_count(question.quiz)

        question = Question.objects.prefetch_related("answer_set").get(pk=question.pk)
        return Response(serialize_question(request, question),
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
