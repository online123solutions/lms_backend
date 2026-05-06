from django.contrib import admin
from django import forms
from .models import (
    CustomUser, TraineeProfile, EmployeeProfile, TrainerProfile,Courses, CourseLesson,Macroplanner,Microplanner,Subject,Lesson,Query,QueryResponse,
    UserLoginActivity,AssessmentReport,Notification,NotificationReceipt,EmployeeLessonCompletion,TraineeLessonCompletion,AdminProfile,SOP,
    StandardLibraryItem,TrainerLessonProgress,TraineeFeedback,TraineeTaskSubmission,Banner,TaskAssignment,Concern,ConcernComment,
    Department,
    )
from django_admin_listfilter_dropdown.filters import DropdownFilter


class DepartmentListFilter(admin.SimpleListFilter):
    title = 'department'
    parameter_name = 'department'

    def lookups(self, request, model_admin):
        return Department

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(department__icontains=f'"{self.value()}"')
        return queryset


class SubjectAdminForm(forms.ModelForm):
    department = forms.MultipleChoiceField(
        choices=Department,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Subject
        fields = '__all__'


class LessonAdminForm(forms.ModelForm):
    department = forms.MultipleChoiceField(
        choices=Department,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Lesson
        fields = '__all__'


class CoursesAdminForm(forms.ModelForm):
    department = forms.MultipleChoiceField(
        choices=Department,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Courses
        fields = '__all__'


class CourseDepartmentListFilter(admin.SimpleListFilter):
    title = 'department'
    parameter_name = 'department'

    def lookups(self, request, model_admin):
        return Department

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(course__department__icontains=f'"{self.value()}"')
        return queryset

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_active')
    search_fields = ('username', 'email')
    list_filter = (
        ('role', DropdownFilter),
        ('is_active', DropdownFilter),
    )
    actions = ['activate_users']

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) successfully activated.")

admin.site.register(TraineeProfile)
admin.site.register(EmployeeProfile)
admin.site.register(TrainerProfile)
admin.site.register(AdminProfile)

@admin.register(Courses)
class CoursesAdmin(admin.ModelAdmin):
    form = CoursesAdminForm
    list_display = ('course_id', 'course_name', 'display_departments', 'is_approved', 'display_on_frontend', 'created_by')
    list_filter = (DepartmentListFilter, 'is_approved')
    search_fields = ('course_id', 'course_name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['created_by']
    ordering = ['-created_at']

    def display_departments(self, obj):
        if isinstance(obj.department, list):
            return ', '.join(obj.department) if obj.department else '-'
        return obj.department or '-'
    display_departments.short_description = 'Departments'


@admin.register(CourseLesson)
class CourseLessonAdmin(admin.ModelAdmin):
    list_display = ('lesson_id', 'lesson_name', 'course', 'is_approved', 'display_on_frontend', 'created_by')
    list_filter = (CourseDepartmentListFilter, 'is_approved', 'course')
    search_fields = ('lesson_id', 'lesson_name', 'course__course_name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['course', 'created_by']
    ordering = ['-created_at']

@admin.register(Macroplanner)
class MacroplannerAdmin(admin.ModelAdmin):
    list_filter = ('department',)

@admin.register(Microplanner)
class MacroplannerAdmin(admin.ModelAdmin):
    list_filter = ('department',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    form = SubjectAdminForm
    list_display = ('name', 'display_departments')
    list_filter = (DepartmentListFilter,)

    def display_departments(self, obj):
        if isinstance(obj.department, list):
            return ', '.join(obj.department) if obj.department else '-'
        return obj.department or '-'
    display_departments.short_description = 'Departments'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    form = LessonAdminForm
    list_display = ('name', 'subject', 'display_departments')
    list_filter = (DepartmentListFilter, 'subject')

    def display_departments(self, obj):
        if isinstance(obj.department, list):
            return ', '.join(obj.department) if obj.department else '-'
        return obj.department or '-'
    display_departments.short_description = 'Departments'

admin.site.register(Query)
admin.site.register(QueryResponse)
admin.site.register(UserLoginActivity)
admin.site.register(AssessmentReport)
class NotificationReceiptInline(admin.TabularInline):
    model = NotificationReceipt
    extra = 1
    autocomplete_fields = ['user']  # if you enable search for users in admin

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('subject', 'notification_type', 'created_at', 'sent_by')
    search_fields = ('subject', 'message', 'sent_by__username')
    inlines = [NotificationReceiptInline]

admin.site.register(EmployeeLessonCompletion)
admin.site.register(TraineeLessonCompletion)

@admin.register(SOP)
class SOPAdmin(admin.ModelAdmin):
    list_display = ("title","recipient_type","department","target_role","created_by","created_at")
    list_filter  = ("recipient_type","department","target_role","created_at")
    search_fields = ("title","note")
    filter_horizontal = ("recipients",)

@admin.register(StandardLibraryItem)
class StandardLibraryItemAdmin(admin.ModelAdmin):
    list_display = ("title", "target_role", "department", "is_active", "created_at")
    list_filter  = ("target_role", "department", "is_active", "created_at")
    search_fields = ("title", "note")
    readonly_fields = ("created_at",)

@admin.register(TrainerLessonProgress)
class TrainerLessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trainer_username", "trainer_name", "trainer_department",
        "course_name_col", "lesson_name_col",
        "status", "percent",
        "started_at", "completed_at", "last_accessed_at",
    )
    list_display_links = ("id", "lesson_name_col")
    ordering = ("-last_accessed_at",)
    list_per_page = 50

    list_filter = (
        "status",
        "trainer__department",
        "lesson__course",
        ("started_at", admin.DateFieldListFilter),
        ("completed_at", admin.DateFieldListFilter),
        ("last_accessed_at", admin.DateFieldListFilter),
    )

    search_fields = (
        "trainer__user__username",
        "trainer__user__first_name",
        "trainer__user__last_name",
        "lesson__lesson_name",
        "lesson__course__course_name",
        "lesson__lesson_id",
        "lesson__course__course_id",
    )

    list_select_related = ("trainer", "trainer__user", "lesson", "lesson__course")
    # Either keep autocomplete (ensure related admins have search_fields)...
    # autocomplete_fields = ("trainer", "lesson")
    # ...or use raw_id_fields to avoid admin.E040:
    raw_id_fields = ("trainer", "lesson")
    date_hierarchy = "last_accessed_at"

    @admin.display(description="Username")
    def trainer_username(self, obj):
        return obj.trainer.user.username

    @admin.display(description="Trainer Name")
    def trainer_name(self, obj):
        u = obj.trainer.user
        full = f"{getattr(u, 'first_name','')} {getattr(u, 'last_name','')}".strip()
        return full or u.username

    @admin.display(description="Department")
    def trainer_department(self, obj):
        return obj.trainer.department

    @admin.display(description="Course")
    def course_name_col(self, obj):
        return getattr(obj.lesson.course, "course_name", f"Course #{obj.lesson.course_id}")

    @admin.display(description="Lesson")
    def lesson_name_col(self, obj):
        return getattr(obj.lesson, "lesson_name", f"Lesson #{obj.lesson_id}")
    
admin.site.register(TraineeFeedback)

@admin.register(TraineeTaskSubmission)
class TraineeTaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "trainee", "department", "status", "marks", "reviewed_by", "submitted_at")
    list_filter = ("status", "department", "submitted_at")
    search_fields = ("trainee__username", "department", "text", "feedback")
    date_hierarchy = "submitted_at"

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "text")

@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "assigned_to",
        "department",
        "status",
        "priority",
        "due_at",
        "is_overdue_display",
        "created_by",
        "created_at",
    )
    list_filter = (
        "status",
        "priority",
        "department",
        "created_by",
    )
    search_fields = (
        "title",
        "instructions",
        "assigned_to__username",
        "department",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "due_at"
    autocomplete_fields = ["assigned_to", "created_by", "submission"]

    fieldsets = (
        ("Task Info", {
            "fields": (
                "title", "instructions", "department", "priority",
                "assigned_to", "created_by", "due_at", "attachment"
            ),
        }),
        ("Evaluation Settings", {
            "fields": ("max_marks", "requires_submission", "submission", "status"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    @admin.display(description="Overdue?", boolean=True)
    def is_overdue_display(self, obj):
        return obj.is_overdue
    
@admin.register(Concern)
class ConcernAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "assigned_to", "department", "priority", "status", "created_at")
    list_filter = ("status", "priority", "department", "category", "created_at")
    search_fields = ("title", "description", "created_by__username", "assigned_to__username", "department", "category")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ["created_by", "assigned_to"]
    ordering = ("-created_at",)

@admin.register(ConcernComment)
class ConcernCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "concern", "author", "internal", "created_at")
    list_filter = ("internal", "created_at")
    search_fields = ("concern__title", "author__username", "message")
    readonly_fields = ("created_at",)
    autocomplete_fields = ["concern", "author"]