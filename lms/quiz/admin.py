from django.contrib import admin
from .models import Quiz, Question, Answer,Result,ResultAnswer
from user.models import CustomUser
from django.contrib.admin import SimpleListFilter

# Inline admin for answers
class AnswerInLine(admin.TabularInline):
    model = Answer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(question__quiz__created_by=request.user)


class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerInLine]
    list_display = ['question_number', 'question']
    list_filter = ['quiz']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        return qs.filter(quiz__created_by=request.user)

class QuizAdmin(admin.ModelAdmin):
    list_display = ['quiz_name', 'topic', 'department','created_by']
    list_filter = ['department','quiz_type']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.pk: 
            obj.created_by = request.user 
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "created_by":
            kwargs["queryset"] = CustomUser.objects.filter(role="teacher")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    
class ResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'date_attempted')
    list_filter = ('quiz__department','quiz__quiz_type', 'date_attempted')  # Direct filters
    search_fields = ('user__username', 'user__trainee__name', 'quiz__quiz_name')

# admin.site.register(Answer)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Quiz, QuizAdmin)
admin.site.register(Result,ResultAdmin)
admin.site.register(ResultAnswer)