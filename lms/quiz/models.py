from django.db import models
from user.models import *

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

class Quiz(models.Model):
    QUIZ_TYPE_CHOICES = [
        ('homework', 'Homework'),
        ('pre-assessment', 'Pre Assessment'),
        ('post-assessment', 'Post Assessment'),
        ('daily-quiz', 'Daily Quiz'),
        ('weekly-quiz', 'Weekly Quiz'),
        ('monthly-quiz', 'Monthly Quiz'),
        ('final-exam', 'Final Exam'),
    ]
    quiz_name=models.CharField(max_length=150)
    topic=models.CharField(max_length=150)
    department=models.CharField(
        max_length=50,
        choices=Department,
        default='IT')
    no_of_questions=models.IntegerField()
    time=models.IntegerField(help_text="duration of the quiz in minutes")
    passing_score_percentage=models.IntegerField(help_text="required score to pass in %")
    date=models.DateTimeField(null=True)
    start_date = models.DateTimeField(blank=True,null=True)
    end_date = models.DateTimeField(blank=True,null=True)  
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_quizzes',blank=True,null=True)
    quiz_type = models.CharField(
        max_length=20,
        choices=QUIZ_TYPE_CHOICES,
        default='homework',
        help_text='Type of quiz (Homework, Pre Assessment, Post Assessment, etc.)'
    )

    def __str__(self):
        return f"{self.quiz_name}-{self.topic}"
    
    def get_questions(self):
        return self.question_set.all()
    
    class Meta:
        verbose_name_plural='Quizzes'

class Question(models.Model):
    question_number=models.IntegerField()
    question=models.CharField(max_length=500)
    quiz=models.ForeignKey(Quiz, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.question)
    
    def get_answers(self):
        return self.answer_set.all()

class Answer(models.Model):
    answer=models.CharField(max_length=500)
    correct=models.BooleanField(default=False)
    question=models.ForeignKey(Question, on_delete=models.CASCADE)

    def __str__(self):
        return f"Answer-{self.answer},Correct-{self.correct}"
    
class Result(models.Model):
    quiz=models.ForeignKey(Quiz, on_delete=models.CASCADE)
    user=models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    score=models.FloatField()
    date_attempted = models.DateTimeField(auto_now_add=True, null=True,blank=True)
    certificate = models.FileField(upload_to='certificates/', blank=True, null=True)
    correct_questions = models.IntegerField(default=0)
    wrong_questions = models.IntegerField(default=0)
    unattempted_questions = models.IntegerField(default=0)
 

    def __str__(self):
        return str(self.user)
    
class ResultAnswer(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.ForeignKey(Answer, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.result.user.username} - Q{self.question.id} - Correct: {self.is_correct}"