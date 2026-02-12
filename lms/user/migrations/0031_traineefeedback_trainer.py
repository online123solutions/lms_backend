# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0030_alter_courses_department_alter_lesson_department_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='traineefeedback',
            name='trainer',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='received_feedbacks',
                to=settings.AUTH_USER_MODEL,
                limit_choices_to={'role': 'trainer'},
                null=True,  # Allow null temporarily for existing records
                blank=True
            ),
        ),
    ]
