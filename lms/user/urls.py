from django.urls import path,include
from .views import (
    RegistrationView,LoginView,UserLogoutView,DownloadUserTemplate,UploadUsersExcelView,mark_notification_read,PasswordResetRequestView,
    PasswordResetConfirmView
)
from .TrainerView import (
    TrainerDashboardView, TrainerCourseView,TrainerCourseLessonView,MacroplannerViewSet, MicroplannerViewSet,AssessmentListCreateView,
    TrainerAssessmentReportView,AssessmentReportUpdateView,EvaluationRemarkView,TrainingReportView,LMSEngagementView,RecentActivityView,
    TrainerQueryListAPIView, TrainerQueryResponseAPIView, TrainerAssignTrainerAPIView,TrainerNotifyView
)

from .TraineeView import (
    SubjectListAPIView, LessonListAPIView, LessonDetailAPIView,TraineeDashboardView,AvailableQuizListAPIView,TraineeQueryCreateAPIView,
    TraineeQueryListAPIView,TraineeQueryResponseAPIView,ContentStartView, ContentEndView,TraineeMacroplannerListAPIView,TraineeMicroplannerListAPIView,
    TraineeLoginActivityAPIView,TraineeNotificationsView
)

from .EmployeeView import (
    EmployeeDashboardView,EmployeeAvailableQuizListAPIView,EmployeeQueryCreateAPIView,EmployeeQueryListAPIView,EmployeeQueryResponseAPIView,
    EmployeeMacroplannerListAPIView,EmployeeMicroplannerListAPIView,EmployeeLoginActivityAPIView,EmployeeNotificationsView,MarkLessonCompletedAPIView
)

from .AdminView import (
    AdminDashboardView,AdminCourseView,AdminCourseLessonView,AdminLMSEngagementView,AdminRecentActivityView,AdminMacroplannerViewSet,
    AdminMicroplannerViewSet,AdminTrainingReportView,AdminAssessmentReportView
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'trainer/macroplanners', MacroplannerViewSet, basename='trainer-macroplanner')
router.register(r'trainer/microplanners', MicroplannerViewSet, basename='trainer-microplanner')

router.register(r'custom_admin/macroplanners', AdminMacroplannerViewSet, basename='admin-macroplanner')
router.register(r'custom_admin/microplanners', AdminMicroplannerViewSet, basename='admin-microplanner')

router.register(r'trainer/training-report', TrainingReportView, basename='training-report')

urlpatterns = [
    path('', include(router.urls)),
    path('account/register/', RegistrationView.as_view(), name='register'),
    path('account/login/', LoginView.as_view(), name='login'), 
    path('account/logout/', UserLogoutView.as_view(), name='logout'),
    path('account/upload/', UploadUsersExcelView.as_view(), name='upload_students_excel'),
    path('account/template/', DownloadUserTemplate.as_view(), name='download_students_template'),
    path('account/password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('account/password-reset-confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),


    #Trainer Urls
    path('trainer/courses/', TrainerCourseView.as_view(), name='courses'), 
    path('trainer/course-lessons/', TrainerCourseLessonView.as_view(), name='course-lessons'),
    path('trainer/assessments/', AssessmentListCreateView.as_view(), name='trainer-assessments'),
    path("trainer/assessment-reports/", TrainerAssessmentReportView.as_view(), name="trainer-assessment-reports"),
    path('trainer/assessment-report/<int:pk>/', AssessmentReportUpdateView.as_view(), name='update-assessment-report'),
    path('trainer/evaluation-remarks/', EvaluationRemarkView.as_view(), name='evaluation-remarks'),
    path('trainer/notifications/send/', TrainerNotifyView.as_view(), name='trainer-send-notification'),
    path('trainer/recent_activity/', RecentActivityView.as_view(), name='teacher_recent_activity'),
    path('trainer/lms-engagement/', LMSEngagementView.as_view(), name='lms-engagement'),
    path('trainer/queries/', TrainerQueryListAPIView.as_view(), name='trainer-query-list'),
    path('trainer/queries/<int:query_id>/response/', TrainerQueryResponseAPIView.as_view(), name='trainer-query-response'),
    path('trainer/queries/<int:query_id>/assign/', TrainerAssignTrainerAPIView.as_view(), name='trainer-query-assign'),
    path('trainer/mark-read/', mark_notification_read, name='trainee-mark-read'),
    # path('trainer/training-report/', TrainingReportView.as_view({'get': 'list'}), name='training-report'),
    path('trainer/<str:username>/', TrainerDashboardView.as_view(), name='teacher-dashboard'),

    # Trainee Urls
    path('trainee/quiz_available', AvailableQuizListAPIView.as_view(), name='quiz_available'),
    path('trainee/queries/', TraineeQueryListAPIView.as_view(), name='trainee-query-list'),
    path('trainee/queries/create/', TraineeQueryCreateAPIView.as_view(), name='trainee-query-create'),
    path('trainee/queries/<int:query_id>/response/', TraineeQueryResponseAPIView.as_view(), name='trainee-query-response'),
    path('trainee/content-start/', ContentStartView.as_view(), name='content-start'),  # For content start time
    path('trainee/content-end/', ContentEndView.as_view(), name='content-end'),        # For content end time
    path("trainee/macroplanners/", TraineeMacroplannerListAPIView.as_view(), name="trainee-macroplanners"),
    path("trainee/microplanners/", TraineeMicroplannerListAPIView.as_view(), name="trainee-microplanners"),
    path('trainee/login-activity/', TraineeLoginActivityAPIView.as_view(), name='trainee-login-activity'),
    path('trainee/notifications/', TraineeNotificationsView.as_view(), name='trainee-notifications'),
    path('trainee/mark-read/', mark_notification_read, name='trainee-mark-read'),
    path('trainee/lessons/<slug:lesson_slug>/complete/', MarkLessonCompletedAPIView.as_view(), name='mark-lesson-completed'),
    path('trainee/<str:username>/', TraineeDashboardView.as_view(), name='trainee-dashboard'),

    # Employee Urls
    path('employee/quiz_available', EmployeeAvailableQuizListAPIView.as_view(), name='quiz_available'),
    path('employee/queries/', EmployeeQueryListAPIView.as_view(), name='employee-query-list'),
    path('employee/queries/create/', EmployeeQueryCreateAPIView.as_view(), name='employee-query-create'),
    path('employee/queries/<int:query_id>/response/', EmployeeQueryResponseAPIView.as_view(), name='employee-query-response'),
    path('employee/content-start/', ContentStartView.as_view(), name='content-start'),  # For content start time
    path('employee/content-end/', ContentEndView.as_view(), name='content-end'),        # For content end time
    path("employee/macroplanners/", EmployeeMacroplannerListAPIView.as_view(), name="employee-macroplanners"),
    path("employee/microplanners/", EmployeeMicroplannerListAPIView.as_view(), name="employee-microplanners"),
    path('employee/login-activity/', EmployeeLoginActivityAPIView.as_view(), name='employee-login-activity'),
    path('employee/notifications/', EmployeeNotificationsView.as_view(), name='employee-notifications'),
    path('employee/mark-read/', mark_notification_read, name='employee-mark-read'),
    path('employee/lessons/<slug:lesson_slug>/complete/', MarkLessonCompletedAPIView.as_view(), name='mark-lesson-completed'),
    path('employee/<str:username>/', EmployeeDashboardView.as_view(), name='employee-dashboard'),


    # Subject and Lesson URLs
    path('curriculum/subjects/', SubjectListAPIView.as_view(), name='subject-list'),
    path('curriculum/lessons/<slug:slug>/', LessonListAPIView.as_view(), name='lesson-list'),
    path('curriculum/lessons/detail/<slug:slug>/', LessonDetailAPIView.as_view(), name='lesson-detail'),

    # Admin Urls
    path('custom_admin/courses/', AdminCourseView.as_view(), name='courses'), 
    path('custom_admin/course-lessons/', AdminCourseLessonView.as_view(), name='course-lessons'),
    path('custom_admin/lms-engagement/', AdminLMSEngagementView.as_view(), name='admin-lms-engagement'),
    path('custom_admin/recent_activity/', AdminRecentActivityView.as_view(), name='admin_recent_activity'),
    path('custom_admin/training-report/', AdminTrainingReportView.as_view({'get': 'list'}), name='admin-training-report'),
    path('custom_admin/assessment-reports/', AdminAssessmentReportView.as_view(), name='admin-assessment-reports'),
    path('custom_admin/<str:username>', AdminDashboardView.as_view(), name='admin-dashboard'),
]
