from django.db import migrations, models


def copy_department_to_list(apps, schema_editor):
    Subject = apps.get_model('user', 'Subject')
    for obj in Subject.objects.all():
        old = obj.department_old or ''
        obj.department = [old] if old else []
        obj.save(update_fields=['department'])

    Lesson = apps.get_model('user', 'Lesson')
    for obj in Lesson.objects.all():
        old = obj.department_old or ''
        obj.department = [old] if old else []
        obj.save(update_fields=['department'])


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0031_traineefeedback_trainer'),
    ]

    operations = [
        # 1. Rename old CharField to a temporary name
        migrations.RenameField(
            model_name='subject',
            old_name='department',
            new_name='department_old',
        ),
        migrations.RenameField(
            model_name='lesson',
            old_name='department',
            new_name='department_old',
        ),
        # 2. Add new JSONField
        migrations.AddField(
            model_name='subject',
            name='department',
            field=models.JSONField(default=list, blank=True, verbose_name='Departments'),
        ),
        migrations.AddField(
            model_name='lesson',
            name='department',
            field=models.JSONField(default=list, blank=True, verbose_name='Departments'),
        ),
        # 3. Data migration: copy old value as single-item list
        migrations.RunPython(copy_department_to_list, migrations.RunPython.noop),
        # 4. Remove old CharField
        migrations.RemoveField(model_name='subject', name='department_old'),
        migrations.RemoveField(model_name='lesson', name='department_old'),
    ]
