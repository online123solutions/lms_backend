from django.contrib import admin
from .models import Quiz, Question, Answer,Result,ResultAnswer
from user.models import CustomUser
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html


def image_preview(image, height=80):
    if not image:
        return "-"
    return format_html('<img src="{}" style="max-height:{}px;" />', image.url, height)

# Inline admin for answers
class AnswerInLine(admin.TabularInline):
    model = Answer
    fields = ['answer', 'answer_image', 'image_preview', 'correct']
    readonly_fields = ['image_preview']

    @admin.display(description='Preview')
    def image_preview(self, obj):
        return image_preview(obj.answer_image)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(question__quiz__created_by=request.user)


class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerInLine]
    list_display = ['question_number', 'question', 'has_image']
    list_filter = ['quiz']
    fields = ['question_number', 'question', 'question_image', 'image_preview', 'quiz', 'allow_custom_answer', 'expected_answer']
    readonly_fields = ['image_preview']

    @admin.display(description='Preview')
    def image_preview(self, obj):
        return image_preview(obj.question_image, height=200)

    @admin.display(description='Image', boolean=True)
    def has_image(self, obj):
        return bool(obj.question_image)

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

    
class ResultAnswerInline(admin.TabularInline):
    """Submitted answers on the result page; tick 'Is correct' to accept a written answer."""
    model = ResultAnswer
    fields = ['question', 'selected_answer', 'custom_answer', 'expected', 'is_correct']
    readonly_fields = ['question', 'selected_answer', 'custom_answer', 'expected']
    extra = 0
    can_delete = False
    verbose_name_plural = "Submitted answers (tick 'Is correct' to accept a written answer, then Save)"

    @admin.display(description='Correct answer')
    def expected(self, obj):
        correct = obj.question.answer_set.filter(correct=True).first()
        return (correct.answer if correct else "") or obj.question.expected_answer or "-"

    def has_add_permission(self, request, obj=None):
        return False


class ResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'date_attempted')
    list_filter = ('quiz__department','quiz__quiz_type', 'date_attempted')  # Direct filters
    search_fields = ('user__username', 'user__trainee__name', 'quiz__quiz_name')
    inlines = [ResultAnswerInline]

    def get_readonly_fields(self, request, obj=None):
        # Score fields are recalculated from the submitted answers on save
        if obj:
            return ('score', 'correct_questions', 'wrong_questions', 'unattempted_questions')
        return ()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if change:
            form.instance.recalculate()

# admin.site.register(Answer)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Quiz, QuizAdmin)
admin.site.register(Result,ResultAdmin)
class ResultAnswerAdmin(admin.ModelAdmin):
    list_display = ['result', 'question', 'selected_answer', 'custom_answer', 'is_correct']
    list_editable = ['is_correct']  # tick to accept a written answer; the score updates
    list_filter = ['is_correct', 'result__quiz']
    search_fields = ['custom_answer', 'result__user__username']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.result.recalculate()


admin.site.register(ResultAnswer, ResultAnswerAdmin)