from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    TraineeSerializer, EmployeeSerializer, TrainerSerializer, AdminSerializer, LoginSerializer,UserExcelUploadSerializer
)
from .models import (
    CustomUser, TraineeProfile, EmployeeProfile, TrainerProfile, AdminProfile,NotificationReceipt
)
from .tasks import send_welcome_email  
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.authtoken.models import Token 
from django.contrib.auth import authenticate
from django.contrib.auth import login,logout
from rest_framework.permissions import IsAuthenticated,AllowAny
import openpyxl
from django.http import HttpResponse
from django.core.files.storage import default_storage
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class RegistrationView(APIView):
    @swagger_auto_schema(
        operation_description="Register a new user based on role (inactive until approved)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["user"],
            properties={
                "user": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "username": openapi.Schema(type=openapi.TYPE_STRING),
                        "email": openapi.Schema(type=openapi.TYPE_STRING, format='email'),
                        "password": openapi.Schema(type=openapi.TYPE_STRING),
                        "role": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            enum=["trainee", "employee", "trainer", "admin"]
                        ),
                    }
                ),
                "employee_id": openapi.Schema(type=openapi.TYPE_STRING),
                "department": openapi.Schema(type=openapi.TYPE_STRING),
                "designation": openapi.Schema(type=openapi.TYPE_STRING),
                "expertise": openapi.Schema(type=openapi.TYPE_STRING),  # For trainer
            }
        ),
        responses={
            201: openapi.Response("User registered successfully (inactive)"),
            400: "Bad Request",
            200: "User updated successfully (inactive)"
        },
    )
    def post(self, request, *args, **kwargs):
        user_data = request.data
        user_info = user_data.get('user', {})

        if not isinstance(user_info, dict):
            return Response({'error': 'Invalid user data format'}, status=status.HTTP_400_BAD_REQUEST)

        role = user_info.get('role')
        username = user_info.get('username')

        serializer_map = {
            'trainee': TraineeSerializer,
            'employee': EmployeeSerializer,
            'trainer': TrainerSerializer,
            'admin': AdminSerializer,
        }

        serializer_class = serializer_map.get(role)
        if not serializer_class:
            return Response({'error': 'Invalid role'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = CustomUser.objects.filter(username=username).first()
                if user:
                    user.email = user_info.get('email', user.email)
                    user.set_password(user_info.get('password'))
                    if user.is_active:
                        user.is_active = False
                    user.save()
                # Use serializer for create/update
                serializer = serializer_class(data=user_data, instance=user, context={'request': request})
                if serializer.is_valid():
                    user_profile = serializer.save()
                    logger.info(f"Profile saved for user {username}: {user_profile}")
                    send_welcome_email.delay(user_info.get('email'))
                    status_code = status.HTTP_201_CREATED if not user else status.HTTP_200_OK
                    return Response(
                        {"message": f"Registration successful for {role}. Awaiting approval."},
                        status=status_code,
                    )
                else:
                    logger.error(f"Validation errors: {serializer.errors}")
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Exception during registration: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class LoginView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: 'Token', 400: 'Bad Request'}
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            if not user.is_active:
                return Response(
                    {"error": "Account is not active. Please contact support."}, 
                    status=status.HTTP_403_FORBIDDEN
                )

            login(request, user)
            token, created = Token.objects.get_or_create(user=user)

            # Determine role-based dashboard URL using user.role
            role = getattr(user, "role", "").lower()

            if role== "admin":
                dashboard_url = f"/admin-dashboard/{user.username}"
            elif role == "trainee":
                dashboard_url = f"/trainee-dashboard/{user.username}"
            elif role == "trainer":
                dashboard_url = f"/trainer-dashboard/{user.username}"
            elif role == "employee":
                dashboard_url = f"/employee-dashboard/{user.username}"
            else:
                dashboard_url = f"/dashboard/{user.username}"  # fallback`

            return Response({
                "token": token.key,
                "username": user.username,
                "role": user.role,
                "is_superuser": user.is_superuser,
                "dashboard_url": dashboard_url,
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
    
class DownloadUserTemplate(APIView):
    def get(self, request, *args, **kwargs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "User Import Template"

        # Header
        ws.append([
            'role',   
            'username',
            'email',
            'password',
            'name',
            'employee_id',
            'department',
            'designation'
        ])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="user_upload_template.xlsx"'
        wb.save(response)
        return response

    
class UploadUsersExcelView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        request_body=UserExcelUploadSerializer,  
        responses={200: "File processed successfully", 400: "Bad Request"},
    )
    def post(self, request):
        if 'excel_file' not in request.FILES:
            return Response({"error": "Excel file is required."}, status=status.HTTP_400_BAD_REQUEST)

        excel_file = request.FILES['excel_file']
        if not excel_file.name.endswith('.xlsx'):
            return Response({"error": "Invalid file type. Upload a .xlsx file."}, status=status.HTTP_400_BAD_REQUEST)

        file_path = default_storage.save('temp/' + excel_file.name, excel_file)
        wb = openpyxl.load_workbook(default_storage.open(file_path))
        sheet = wb.active

        success_count = 0
        error_count = 0
        errors = []

        for index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            try:
                role, username, name, email, password, employee_id, department, designation= row

                if not all([role, username,name, email, password, employee_id, department, designation]):
                    raise ValueError("Missing required fields.")

                if role not in ['trainee', 'employee', 'trainer', 'admin']:
                    raise ValueError(f"Invalid role: {role}")

                user, created = CustomUser.objects.get_or_create(username=username, email=email)
                if created:
                    user.set_password(password)
                    user.role = role
                    user.is_active = False
                    user.save()

                    # Create appropriate profile
                    if role == 'trainee':
                        TraineeProfile.objects.create(
                            user=user,
                            employee_id=employee_id,
                            department=department,
                            designation=designation
                        )
                    elif role == 'employee':
                        EmployeeProfile.objects.create(
                            user=user,
                            employee_id=employee_id,
                            department=department,
                            designation=designation
                        )
                    elif role == 'trainer':
                        TrainerProfile.objects.create(
                            user=user,
                            employee_id=employee_id,
                            department=department
                        )
                    elif role == 'admin':
                        AdminProfile.objects.create(
                            user=user,
                            employee_id=employee_id,
                            department=department
                        )

                    send_welcome_email.delay(email)
                    success_count += 1
                else:
                    raise ValueError(f"User already exists: {username}")

            except Exception as e:
                error_count += 1
                errors.append(f"Row {index}: {str(e)}")

        return Response({
            "message": f"{success_count} user(s) registered successfully.",
            "errors": errors
        }, status=status.HTTP_200_OK)
    
@swagger_auto_schema(
    method='post',
    operation_description="Mark a notification as read for the current user.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={"notification_id": openapi.Schema(type=openapi.TYPE_INTEGER)},
        required=["notification_id"]
    ),
    responses={200: "OK", 404: "Not Found"}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request):
    nid = request.data.get('notification_id')
    if not nid:
        return Response({"error": "notification_id is required"}, status=400)
    try:
        rec = NotificationReceipt.objects.get(notification_id=nid, user=request.user)
    except NotificationReceipt.DoesNotExist:
        return Response({"error": "Notification not found for this user."}, status=404)

    if not rec.is_read:
        rec.is_read = True
        rec.read_at = timezone.now()
        rec.save(update_fields=['is_read', 'read_at'])

    return Response({"message": "Marked as read."}, status=200)