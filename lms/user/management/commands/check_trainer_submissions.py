from django.core.management.base import BaseCommand
from user.models import CustomUser, TrainerProfile, TraineeTaskSubmission


class Command(BaseCommand):
    help = 'Check trainer department and available submissions'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Trainer username')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = CustomUser.objects.get(username=username)
            self.stdout.write(f'User: {user.username}')
            self.stdout.write(f'Role: {user.role}')
            
            if user.role != 'trainer':
                self.stdout.write(self.style.ERROR(f'User is not a trainer!'))
                return
            
            trainer_profile = TrainerProfile.objects.get(user=user)
            trainer_dept = trainer_profile.department
            self.stdout.write(f'Trainer Department: {trainer_dept}')
            
            # Apply department mapping
            department_mapping = {
                "Development": "Training",
                "Shop Editing": "Shop Editor Training"
            }
            mapped_dept = department_mapping.get(trainer_dept, trainer_dept)
            self.stdout.write(f'Mapped Department (what trainer should see): {mapped_dept}')
            
            # Check submissions
            self.stdout.write(f'\n=== All Submissions ===')
            all_subs = TraineeTaskSubmission.objects.all()
            for sub in all_subs:
                self.stdout.write(f'ID: {sub.id}, Trainee: {sub.trainee.username}, Dept: "{sub.department}"')
            
            # Check matching submissions
            self.stdout.write(f'\n=== Submissions matching "{mapped_dept}" ===')
            matching_subs = TraineeTaskSubmission.objects.filter(department__iexact=mapped_dept)
            self.stdout.write(f'Found {matching_subs.count()} matching submissions')
            for sub in matching_subs:
                self.stdout.write(f'ID: {sub.id}, Trainee: {sub.trainee.username}, Dept: "{sub.department}", Status: {sub.status}')
            
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {username} not found'))
        except TrainerProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Trainer profile not found for {username}'))
