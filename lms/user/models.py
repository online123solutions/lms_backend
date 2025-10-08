from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import os
from django.utils.text import slugify
from django.urls import reverse
from django.db.models import Q
from .tasks import send_email_to_trainer
from django.utils import timezone
from django.db.models import Avg
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('trainee', 'Trainee'),
        ('employee', 'Employee'),
        ('trainer', 'Trainer'),
        ('admin', 'Admin'),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='trainee',
        help_text="Select the role of the user."
    )

    email = models.EmailField(
        max_length=254,
        unique=True,
        error_messages={
            'unique': "A user with that email already exists.",
        }
    )


class TraineeProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='trainee_profile')
    name= models.CharField(max_length=100,default="")
    employee_id = models.CharField(max_length=20)
    department = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    trainer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_trainees')
    profile_picture = models.ImageField(upload_to='trainee_profiles/', default='default_profile.jpg', null=True, blank=True)

    def __str__(self):
        return f"Trainee: {self.user.username}"
    
    class Meta:
        verbose_name = "Trainee Profile"
        verbose_name_plural = "Trainee Profiles"
        ordering = ['user__username']
  

class EmployeeProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='employee_profile')
    name= models.CharField(max_length=100,default="")
    employee_id = models.CharField(max_length=20)
    department = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='employee_profiles/', default='default_profile.jpg', null=True, blank=True)

    def __str__(self):
        return f"Employee: {self.user.username}"

    class Meta:
        verbose_name = "Employee Profile"
        verbose_name_plural = "Employee Profiles"
        ordering = ['user__username']


class TrainerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='trainer_profile')
    name= models.CharField(max_length=100,default="")
    employee_id = models.CharField(max_length=20)
    department = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    expertise = models.TextField(blank=True)  # topics or designations they handle
    profile_picture = models.ImageField(upload_to='trainer_profiles/', default='default_profile.jpg', null=True, blank=True)


    def __str__(self):
        return f"Trainer: {self.user.username}"
    
    class Meta:
        verbose_name = "Trainer Profile"
        verbose_name_plural = "Trainer Profiles"
        ordering = ['user__username']


class AdminProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='admin_profile')
    name= models.CharField(max_length=100,default="")
    employee_id = models.CharField(max_length=20)
    department = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='admin_profiles/', default='default_profile.jpg', null=True, blank=True)

    def __str__(self):
        return f"Admin: {self.user.username}"
    

Department=[
    ('HR', 'Human Resources'),
    ('IT', 'Information Technology'),
    ('Finance', 'Finance'),
    ('Marketing', 'Marketing'),
    ('Sales', 'Sales'),
    ('Operations', 'Operations'),
    ('Support', 'Support'),
    ('Training', 'Training'),
    ('Development', 'Development'),
    ('Design', 'Design'),
]
MONTH_CHOICES = [
    ('January', 'January'),
    ('February', 'February'),
    ('March', 'March'),
    ('April', 'April'),
    ('May', 'May'),
    ('June', 'June'),
    ('July', 'July'),
    ('August', 'August'),
    ('September', 'September'),
    ('October', 'October'),
    ('November', 'November'),
    ('December', 'December'),
]


class Courses(models.Model):
    course_id=models.CharField(max_length=100,unique=True)
    course_name=models.CharField(max_length=100)
    department=models.CharField(max_length=100,choices=Department)
    display_on_frontend = models.BooleanField(default=True, verbose_name="Display on Frontend")
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'trainer'},
        related_name='created_courses'
    )

    is_approved = models.BooleanField(default=False, help_text="Approve this course for employee/trainee visibility.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.course_name
    

class CourseLesson(models.Model):
    lesson_id=models.CharField(max_length=100,unique=True)
    lesson_name=models.CharField(max_length=100)
    course=models.ForeignKey(Courses,on_delete=models.CASCADE,related_name='lessons')
    lesson_video=models.URLField(verbose_name="Lesson Videos", max_length=300, default="", null=True, blank=True)
    lesson_plans=models.FileField(upload_to='lesson_plans/',blank=True)
    lesson_ppt=models.FileField(upload_to='lesson_ppts/',blank=True)
    lesson_editor=models.URLField(blank=True)
    display_on_frontend = models.BooleanField(default=True, verbose_name="Display on Frontend")

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'trainer'},
        related_name='created_lessons'
    )

    is_approved = models.BooleanField(default=False, help_text="Approve this lesson for employee/trainee visibility.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.lesson_name
    
class Macroplanner(models.Model):
    duration_choices = [
        ('1 Month', '1 Month'),
        ('2 Months', '2 Months'),
        ('3 Months', '3 Months'),
        ('4 Months', '4 Months'),
        ('5 Months', '5 Months'),
        ('6 Months', '6 Months'),
    ]
    weeks = [
        ('week 1', 'Week 1'),
        ('week 2', 'Week 2'),
        ('week 3', 'Week 3'),
        ('week 4', 'Week 4'),
    ]
    MODE_CHOICES = [
        ('Theoretical', 'Theoretical'),
        ('Practical', 'Practical'),
    ]
    ROLE_CHOICES = [
    ('trainee', 'Trainee'),
    ('employee', 'Employee'),
    ]
    duration= models.CharField(max_length=20, choices=duration_choices, default='1 Month')
    month=models.CharField(max_length=100,choices=MONTH_CHOICES)
    week=models.CharField(max_length=100,default="",choices=weeks)
    department=models.CharField(max_length=100,choices=Department)
    module=models.CharField(max_length=100,default="")
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='Theoretical')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='trainee', db_index=True)

    def __str__(self):
        return f"Macroplanner - User: {self.department}, File: {self.month}"
    

class Microplanner(models.Model):
    weeks = [
        ('Week 1', 'Week 1'),
        ('Week 2', 'Week 2'),
        ('Week 3', 'Week 3'),
        ('Week 4', 'Week 4'),
    ]
    MODE_CHOICES = [
        ('Theoretical', 'Theoretical'),
        ('Practical', 'Practical'),
    ]
    ROLE_CHOICES = [
    ('trainee', 'Trainee'),
    ('employee', 'Employee'),
    ]
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    week= models.CharField(max_length=100, choices=weeks)
    days= models.CharField(max_length=100,default="")
    department=models.CharField(max_length=100,choices=Department)
    no_of_sessions = models.PositiveIntegerField(default="")
    name_of_topic = models.JSONField(default=list, blank=True, null=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='Theoretical')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='trainee', db_index=True)

    class Meta:
        verbose_name_plural = "Microplanners"
        unique_together = ["department", "month", "name_of_topic"]

    def __str__(self):
        return f"{self.department} - {self.month} - {self.name_of_topic}"


class Assessment(models.Model):
    ASSESSMENT_TYPE = [
        ('task', 'Task'),
        ('quiz', 'Quiz'),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(max_length=10, choices=ASSESSMENT_TYPE, default='task')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trainer_assessments')
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()

    def __str__(self):
        return self.title
    

class EvaluationRemark(models.Model):
    trainee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='evaluation_remarks')
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_remarks')
    assessment = models.ForeignKey('Assessment', on_delete=models.SET_NULL, null=True, blank=True)
    overall_feedback = models.TextField()
    strengths = models.TextField(blank=True)
    improvement_areas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Remark by {self.trainer.username} for {self.trainee.username}"

class TrainingReport(models.Model):
    trainee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Courses, on_delete=models.CASCADE)
    completed_lessons = models.PositiveIntegerField(default=0)
    total_lessons = models.PositiveIntegerField(default=0)
    average_score = models.FloatField(default=0.0)
    participation_rate = models.FloatField(default=0.0)
    last_accessed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.trainee.username} - {self.course.course_name}"
    
class UserLoginActivity(models.Model):
    # Login Status
    SUCCESS = 'S'
    FAILED = 'F'

    LOGIN_STATUS = ((SUCCESS, 'Success'),
                           (FAILED, 'Failed'))

    login_IP = models.GenericIPAddressField(null=True, blank=True)
    login_datetime = models.DateTimeField()
    login_username = models.CharField(max_length=40, null=True, blank=True)
    status = models.CharField(max_length=1, default=SUCCESS, choices=LOGIN_STATUS, null=True, blank=True)
    user_agent_info = models.CharField(max_length=255)
    login_num=models.CharField(max_length=1000,default=0)

    class Meta:
        verbose_name = 'User Login Activity'
        verbose_name_plural = 'User Login Activities'
        
    def get_trainee_name(self):
        try:
            trainee_profile = TraineeProfile.objects.get(user__username=self.login_username)
            return f"{trainee_profile.name}"
        except TraineeProfile.DoesNotExist:
            return None

    def __str__(self):
        return self.login_username
    

class Query(models.Model):
    CATEGORY_CHOICES = [
        ('assessment', 'Assessment'),
        ('training', 'Training'),
        ('general', 'General'),
    ]
    
    RAISED_BY_CHOICES = [
        ('trainee', 'Trainee'),
        ('employee', 'Employee'),
    ]
    
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='raised_queries')
    assigned_trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_queries')
    question = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    raised_by_role = models.CharField(max_length=20, choices=RAISED_BY_CHOICES, default='employee')  # Trainee or Employee
    department = models.CharField(max_length=100,choices=Department,default="IT")  # To store the department of the person who raised the query

    def __str__(self):
        return f"Query by {self.raised_by.username} - {self.question[:30]}"
    
    def notify_trainer(self):
        """
        Notify the trainer of the new query asynchronously.
        """
        try:
            # Fetch the trainer profile based on the department
            trainer_profile = TrainerProfile.objects.filter(department=self.department).first()
            
            if trainer_profile:
                trainer = trainer_profile.user  # Get the trainer (CustomUser) from TrainerProfile
                
                # Send email to trainer asynchronously using Celery
                send_email_to_trainer.delay(
                    subject='New Query Raised',
                    message=f'A new query has been raised in your department: {self.question}',
                    email=trainer.email
                )
            else:
                print(f"No trainer found in the {self.department} department.")
        except Exception as e:
            print(f"Error in notifying trainer: {str(e)}")


class QueryResponse(models.Model):
    query = models.ForeignKey(Query, on_delete=models.CASCADE, related_name='responses')
    responder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    response = models.TextField()
    responded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response by {self.responder.username} on Query {self.query.id}"


def save_subject_image(instance, filename):
    upload_to = 'Images/'
    ext = filename.split('.')[-1]
    # get filename
    if instance.subject_id:
        filename = 'Subject_Pictures/{}.{}'.format(instance.subject_id, ext)
    return os.path.join(upload_to, filename)

class Subject(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(null=True, blank=True)
    department = models.CharField(max_length=50, choices=Department, default='IT', verbose_name='Department')
    image = models.ImageField(upload_to=save_subject_image, blank=True, verbose_name='Subject Image')
    description = models.TextField(max_length=500,blank=True)
    display_on_frontend = models.BooleanField(default=True, verbose_name="Display on Frontend")
    is_new = models.BooleanField(default=False, help_text="Mark as new for employee dashboard visibility")
    
    class Meta:
        verbose_name_plural = '2. Subjects'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        

def save_lesson_files(instance, filename):
    upload_to = 'Images/'
    ext = filename.split('.')[-1]
    # get filename
    if instance.lesson_id:
        filename = 'lesson_files/{}/{}.{}'.format(instance.lesson_id,instance.lesson_id, ext)
        if os.path.exists(filename):
            new_name = str(instance.lesson_id) + str('1')
            filename =  'lesson_images/{}/{}.{}'.format(instance.lesson_id,new_name, ext)
    return os.path.join(upload_to, filename)

class Lesson(models.Model):
    lesson_id = models.CharField(max_length=100, unique=True)
    department = models.CharField(max_length=50, choices=Department, default='IT', verbose_name='Department')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='lessons')
    name = models.CharField(max_length=250)
    position = models.PositiveSmallIntegerField(verbose_name="Chapter no.")
    slug = models.SlugField(null=True, blank=True, unique=True)
    tutorial_video = models.URLField(verbose_name="Videos", max_length=300, default="", null=True, blank=True)
    quiz = models.URLField(verbose_name="Quiz", max_length=300, default="", null=True, blank=True)
    content = models.URLField(verbose_name="Learning Aids", max_length=300, default="", null=True, blank=True)
    editor = models.URLField(verbose_name="Editor", max_length=300, default="", null=True, blank=True)
    display_on_frontend = models.BooleanField(default=True, verbose_name="Display on Frontend")
    mark_as_completed=models.BooleanField(verbose_name="Mark as completed",default=False)
    is_new = models.BooleanField(default=False, help_text="Mark as new for employee dashboard visibility")

    class Meta:
        ordering = ['position']
        verbose_name_plural = '3. Lessons'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Automatically generate slug from name before saving."""
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Return the URL to access the lesson detail view."""
        return reverse('curriculum:lesson_list', kwargs={'slug': self.subject.slug})
    
class AssessmentReport(models.Model):
    REPORT_TYPES = [
        ('homework', 'Homework'),
        ('pre-assessment', 'Pre Assessment'),
        ('post-assessment', 'Post Assessment'),
        ('daily-quiz', 'Daily Quiz'),
        ('weekly-quiz', 'Weekly Quiz'),
        ('monthly-quiz', 'Monthly Quiz'),
        ('final-exam', 'Final Exam'),
    ]

    AUDIENCE = [
        ('trainee', 'Trainee'),
        ('employee', 'Employee'),
    ]

    quiz = models.ForeignKey('quiz.Quiz', on_delete=models.CASCADE,
                             related_name="assessment_reports")

    # NEW: who this report targets (so the same structure works for both)
    audience = models.CharField(max_length=10, choices=AUDIENCE,
                                default='trainee', db_index=True)

    total_trainee = models.IntegerField(default=0)       # keep existing names
    trainee_attempted = models.IntegerField(default=0)   # (used for both audiences)
    average_score = models.FloatField(default=0.0)
    completion_rate = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    # FIX: default must be one of the choices
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES,
                                   default='daily-quiz')

    def update_report(self):
        """
        Recompute totals and averages for the configured audience in the quiz's department.
        """
        from quiz.models import Result  # your Result model

        # total population by audience (same department as the quiz)
        if self.audience == 'trainee':
            population_qs = TraineeProfile.objects.filter(
                department=self.quiz.department, user__is_active=True
            )
            # results joined via the user who has a trainee_profile in that dept
            results_qs = Result.objects.filter(
                quiz=self.quiz,
                user__trainee_profile__department=self.quiz.department,
                user__is_active=True
            )
        else:  # employee
            population_qs = EmployeeProfile.objects.filter(
                department=self.quiz.department, user__is_active=True
            )
            results_qs = Result.objects.filter(
                quiz=self.quiz,
                user__employee_profile__department=self.quiz.department,
                user__is_active=True
            )

        self.total_trainee = population_qs.count()
        self.trainee_attempted = results_qs.count()
        self.average_score = round(results_qs.aggregate(avg=Avg('score'))['avg'] or 0, 2)
        self.completion_rate = round(
            (self.trainee_attempted / self.total_trainee) * 100 if self.total_trainee else 0, 2
        )
        self.last_updated = timezone.now()
        self.save(update_fields=[
            'total_trainee', 'trainee_attempted', 'average_score',
            'completion_rate', 'last_updated'
        ])

    def __str__(self):
        return f"{self.report_type} ({self.audience}) - {self.quiz.quiz_name} - {self.quiz.department}"
    

class Notification(models.Model):
    TYPE_CHOICES = [
        ('assessment', 'Assessment'),
        ('module', 'Module'),
        ('info', 'General Info'),
    ]

    subject = models.CharField(max_length=255, default="Notification")
    message = models.TextField()
    link = models.URLField(blank=True, null=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    created_at = models.DateTimeField(auto_now_add=True)

    # who sent it (any role) -> always store the base User
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications_sent'
    )

    # recipients (any mix of roles) with per-user read status via through model
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='NotificationReceipt',
        related_name='notifications_received'
    )

    def __str__(self):
        return f"{self.subject} ({self.notification_type})"


class NotificationReceipt(models.Model):
    """Per-recipient delivery + read state."""
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # nice-to-haves
    delivered_at = models.DateTimeField(auto_now_add=True)
    archived = models.BooleanField(default=False)

    class Meta:
        unique_together = ('notification', 'user')   # one row per recipient
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification']),
        ] 

class EmployeeLessonCompletion(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="lesson_completions")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="completions")
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'lesson')  # Prevent duplicates

    def __str__(self):
        return f"{self.employee.user.username} - {self.lesson.name} - Completed: {self.completed}"   
    
class TraineeLessonCompletion(models.Model):
    trainee = models.ForeignKey(TraineeProfile, on_delete=models.CASCADE, related_name='lesson_completions')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)  # Adjust 'Lesson' to your model name
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('trainee', 'lesson')  # Prevent duplicate completions

    def __str__(self):
        return f"{self.trainee.user.username} - {self.lesson.name} - Completed: {self.completed}"


PROFILE_TYPE_CHOICES = (
    ('trainee', 'Trainee'),
    ('employee','Employee'),
    ('trainer', 'Trainer'),
    ('admin',   'Admin'),
)

RECIPIENT_TYPE_CHOICES = (
    ("GROUP", "Group"),
    ("INDIVIDUAL", "Individual"),
)

def validate_pdf_mimetype(f):
    ct = getattr(f, "content_type", None)
    if ct and ct not in ("application/pdf", "application/x-pdf"):
        raise ValidationError("Only PDF files are allowed.")

def validate_max_size_10mb(f):
    if f.size > 10 * 1024 * 1024:
        raise ValidationError("File too large (max 10 MB).")

class SOP(models.Model):
    title = models.CharField(max_length=200)
    note  = models.TextField(blank=True)

    recipient_type = models.CharField(
        max_length=12, choices=RECIPIENT_TYPE_CHOICES, default="GROUP"
    )

    # For GROUP targeting (wildcards allowed by leaving blank)
    department  = models.CharField(max_length=32, choices=Department, blank=True)
    target_role = models.CharField(max_length=20, choices=PROFILE_TYPE_CHOICES, blank=True)

    # For INDIVIDUAL targeting
    recipients = models.ManyToManyField(CustomUser, blank=True, related_name="sops_received")

    file = models.FileField(
        upload_to="sops/%Y/%m/",
        validators=[FileExtensionValidator(["pdf"]), validate_pdf_mimetype, validate_max_size_10mb],
        help_text="Upload PDF (max 10 MB)."
    )

    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="sops_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.recipient_type})"

    def clean(self):
        if self.recipient_type == "GROUP":
            if not self.department and not self.target_role:
                raise ValidationError("For GROUP, select at least Department or Role.")
            

class StandardLibraryItem(models.Model):
    title = models.CharField(max_length=200)
    note  = models.TextField(blank=True)

    # Library is GROUP/global only (no recipients M2M)
    department  = models.CharField(max_length=32, choices=Department, blank=True)
    target_role = models.CharField(max_length=20, choices=PROFILE_TYPE_CHOICES, blank=True)

    file = models.FileField(
        upload_to="library/%Y/%m/",
        validators=[FileExtensionValidator(["pdf"]), validate_pdf_mimetype, validate_max_size_10mb],
        help_text="Upload PDF (max 10 MB)."
    )

    # Optional metadata
    tags = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="library_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Standard Library Item"
        verbose_name_plural = "Standard Library"

    def __str__(self):
        return self.title
    
class TrainerLessonProgress(models.Model):
    """
    One row per (trainer, lesson). Tracks start/completion.
    """
    trainer = models.ForeignKey(TrainerProfile, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(CourseLesson, on_delete=models.CASCADE, related_name="trainer_progress")

    # Basic lifecycle flags
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Optional status & percent for richer UI
    STATUS_CHOICES = (
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_started")
    percent = models.PositiveSmallIntegerField(default=0)  # 0..100
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("trainer", "lesson")
        indexes = [
            models.Index(fields=["trainer", "lesson"]),
            models.Index(fields=["status"]),
        ]

    def mark_started(self):
        if not self.started_at:
            self.started_at = timezone.now()
        if self.status == "not_started":
            self.status = "in_progress"

    def mark_completed(self):
        self.completed_at = timezone.now()
        self.status = "completed"
        self.percent = 100

class TraineeFeedback(models.Model):
    trainee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="feedbacks")
    communication = models.PositiveSmallIntegerField(default=0)
    subject_knowledge = models.PositiveSmallIntegerField(default=0)
    mentorship = models.PositiveSmallIntegerField(default=0)
    custom_feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.trainee.username} on {self.created_at.date()}"
    
class TraineeTaskSubmission(models.Model):
    STATUS_SUBMITTED = "submitted"
    STATUS_REVIEWED  = "reviewed"
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_REVIEWED,  "Reviewed"),
    ]

    trainee = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="trainee_task_submissions"
    )
    department   = models.CharField(max_length=120, blank=True)   # optional
    text         = models.TextField(blank=True)                   # optional
    file         = models.FileField(upload_to="trainee_tasks/%Y/%m/%d/", blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # --- Review fields ---
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    marks       = models.PositiveSmallIntegerField(null=True, blank=True)  # 0..100 (typical)
    feedback    = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        TrainerProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="trainee_task_reviews"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_file = models.FileField(upload_to="trainee_tasks/reviews/%Y/%m/%d/", blank=True, null=True)

    class Meta:
        ordering = ("-submitted_at",)

    def __str__(self):
        return f"Submission #{self.pk} by {self.trainee} ({self.department or '-'})"
    
class Banner(models.Model):
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to="banners/")  # requires Pillow
    text = models.TextField(blank=True)              # overlay/description text
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title