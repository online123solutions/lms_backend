from django.core.management.base import BaseCommand
from user.models import TaskAssignment


class Command(BaseCommand):
    help = 'Normalize department names in existing TaskAssignment records'

    def handle(self, *args, **options):
        tasks = TaskAssignment.objects.all()
        updated_count = 0
        
        self.stdout.write(self.style.WARNING(f'Found {tasks.count()} task assignments to check'))
        
        for task in tasks:
            old_dept = task.department
            # Call the normalize method
            if task.department:
                normalized = task._normalize_department(task.department)
                if normalized != old_dept:
                    task.department = normalized
                    task.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Task #{task.id}: "{old_dept}" → "{normalized}"')
                    )
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
        self.stdout.write(self.style.SUCCESS(f'Total tasks checked: {tasks.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Departments normalized: {updated_count}'))
