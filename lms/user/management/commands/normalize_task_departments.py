from django.core.management.base import BaseCommand
from user.models import TaskAssignment, TraineeTaskSubmission


class Command(BaseCommand):
    help = 'Normalize department names in existing TaskAssignment and TraineeTaskSubmission records'

    def handle(self, *args, **options):
        # Normalize TaskAssignment records
        tasks = TaskAssignment.objects.all()
        task_updated_count = 0
        
        self.stdout.write(self.style.WARNING(f'Found {tasks.count()} task assignments to check'))
        
        for task in tasks:
            old_dept = task.department
            if task.department:
                normalized = task._normalize_department(task.department)
                if normalized != old_dept:
                    task.department = normalized
                    task.save()
                    task_updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ TaskAssignment #{task.id}: "{old_dept}" → "{normalized}"')
                    )
        
        # Normalize TraineeTaskSubmission records
        submissions = TraineeTaskSubmission.objects.all()
        submission_updated_count = 0
        
        self.stdout.write(self.style.WARNING(f'\nFound {submissions.count()} trainee task submissions to check'))
        
        for submission in submissions:
            old_dept = submission.department
            if submission.department:
                normalized = submission._normalize_department(submission.department)
                if normalized != old_dept:
                    submission.department = normalized
                    submission.save()
                    submission_updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Submission #{submission.id}: "{old_dept}" → "{normalized}"')
                    )
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
        self.stdout.write(self.style.SUCCESS(f'TaskAssignments checked: {tasks.count()}'))
        self.stdout.write(self.style.SUCCESS(f'TaskAssignments normalized: {task_updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'Submissions checked: {submissions.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Submissions normalized: {submission_updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'Total normalized: {task_updated_count + submission_updated_count}'))
