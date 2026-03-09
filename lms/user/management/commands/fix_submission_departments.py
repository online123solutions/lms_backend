from django.core.management.base import BaseCommand
from user.models import TraineeTaskSubmission


class Command(BaseCommand):
    help = 'Update all TraineeTaskSubmission departments from Training to Shop Editor Training'

    def handle(self, *args, **options):
        # Update all submissions that are currently "Training" to "Shop Editor Training"
        submissions = TraineeTaskSubmission.objects.filter(department="Training")
        count = submissions.count()
        
        self.stdout.write(self.style.WARNING(f'Found {count} submissions with department="Training"'))
        
        if count > 0:
            updated = submissions.update(department="Shop Editor Training")
            self.stdout.write(self.style.SUCCESS(f'✓ Updated {updated} submissions to "Shop Editor Training"'))
        else:
            self.stdout.write(self.style.WARNING('No submissions to update'))
        
        # Show current department distribution
        self.stdout.write(self.style.SUCCESS(f'\n=== Current Department Distribution ==='))
        all_submissions = TraineeTaskSubmission.objects.all()
        dept_counts = {}
        for sub in all_submissions:
            dept = sub.department or "(empty)"
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        
        for dept, count in dept_counts.items():
            self.stdout.write(f'{dept}: {count}')
