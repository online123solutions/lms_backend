from rest_framework import serializers
from .models import Quiz, Question, Answer,Result

class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = "__all__"

class QuestionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True, source='get_answers')

    class Meta:
        model = Question
        fields = "__all__"

class QuizSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True) 
    questions = QuestionSerializer(many=True, read_only=True, source='get_questions')

    class Meta:
        model = Quiz
        fields = ["id", "topic", "department","quiz_type", "questions"]

        
class ResultSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='user.trainee.name', read_only=True)
    employee_department=serializers.CharField(source='user.trainee.department', read_only=True)
    employee_username = serializers.CharField(source='user.username', read_only=True)
    score = serializers.SerializerMethodField()
    
    class Meta:
        model=Result
        fields = ['id', 'employee_name','employee_department','employee_username', 'score', 'quiz', 'date_attempted']

    def get_score(self, obj):
        return round(obj.score, 2)
