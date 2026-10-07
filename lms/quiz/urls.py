from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .manage_views import QuestionManageViewSet, QuizManageViewSet
from .views import (
    QuizListAPIView, QuizDetailAPIView, QuizDataAPIView, QuizResultAPIView,
    QuizAttemptDetailAPIView, ResultAnswerMarkAPIView,
)

# Admin dashboard: manage quizzes/questions (must come before the '<pk>/' routes)
manage_router = DefaultRouter()
manage_router.register(r'quizzes', QuizManageViewSet, basename='manage-quiz')
manage_router.register(r'questions', QuestionManageViewSet, basename='manage-question')

urlpatterns = [
    path('manage/', include(manage_router.urls)),
    path('', QuizListAPIView.as_view(), name="quiz_list_api"),  # List of quizzes
    path('result-answers/<int:pk>/', ResultAnswerMarkAPIView.as_view(), name="result_answer_mark_api"),  # Admin/trainer marks an answer
    path('<pk>/', QuizDetailAPIView.as_view(), name="quiz_detail_api"),  # Quiz details
    path('<pk>/data/', QuizDataAPIView.as_view(), name="quiz_data_api"),  # Fetch quiz questions and answers
    path('<pk>/save/', QuizResultAPIView.as_view(), name="quiz_result_api"),
    path('<pk>/attempts/<str:username>/', QuizAttemptDetailAPIView.as_view(), name="quiz_attempt_detail_api"),  # A user's answers, for review
]
