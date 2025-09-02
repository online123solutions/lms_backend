from django.contrib import admin
from .models import (
    CustomUser, TraineeProfile, EmployeeProfile, TrainerProfile,Courses, CourseLesson,Macroplanner,Microplanner,Subject,Lesson,Query,QueryResponse,
    UserLoginActivity,AssessmentReport,Notification,NotificationReceipt,EmployeeLessonCompletion,TraineeLessonCompletion,AdminProfile
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