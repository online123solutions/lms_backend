from django.contrib import admin
from .models import (
    CustomUser, TraineeProfile, EmployeeProfile, TrainerProfile,Courses, CourseLesson,Macroplanner,Microplanner,Subject,Lesson,Query,QueryResponse,
    UserLoginActivity,AssessmentReport,Notification,NotificationReceipt,EmployeeLessonCompletion,TraineeLessonCompletion,AdminProfile,SOP,
    StandardLibraryItem,TrainerLessonProgress,TraineeFeedback
    )
from django_admin_listfilter_dropdown.filters import DropdownFilter

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
    list_display = ('course_id', 'course_name', 'department', 'is_approved', 'display_on_frontend', 'created_by')
    list_filter = ('department', 'is_approved')
    search_fields = ('course_id', 'course_name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['created_by']
    ordering = ['-created_at']


@admin.register(CourseLesson)
class CourseLessonAdmin(admin.ModelAdmin):
    list_display = ('lesson_id', 'lesson_name', 'course', 'is_approved', 'display_on_frontend', 'created_by')
    list_filter = ('course__department', 'is_approved', 'course')
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
    list_display=('name','department')
    list_filter=('department',)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display=('name','subject','department')
    list_filter=('department','subject')

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