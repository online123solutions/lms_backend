from django.db import migrations, models


def copy_department_to_list(apps, schema_editor):
    Courses = apps.get_model('user', 'Courses')
    for obj in Courses.objects.all():
        old = obj.department_old or ''
        obj.department = [old] if old else []
        obj.save(update_fields=['department'])


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0032_subject_lesson_department_jsonfield'),
    ]

    operations = [
        # 1. Rename old CharField to temporary name
        migrations.RenameField(
            model_name='courses',
            old_name='department',
            new_name='department_old',
        ),
        # 2. Add new JSONField
        migrations.AddField(
            model_name='courses',
            name='department',
            field=models.JSONField(default=list, blank=True, verbose_name='Departments'),
        ),
        # 3. Data migration: copy old value as single-item list
        migrations.RunPython(copy_department_to_list, migrations.RunPython.noop),
        # 4. Remove old CharField
        migrations.RemoveField(model_name='courses', name='department_old'),
    ]
