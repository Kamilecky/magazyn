from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pracownicy', '0008_replace_system'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrzydzialDzienny',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dane', models.JSONField(verbose_name='Dane przydziału')),
                ('data_przydzialu', models.DateTimeField(auto_now=True, verbose_name='Data przydziału')),
                ('plan', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='przydzial',
                    to='pracownicy.plandzienny',
                    verbose_name='Plan',
                )),
            ],
            options={
                'verbose_name': 'Przydział dzienny',
                'verbose_name_plural': 'Przydziały dzienne',
            },
        ),
    ]
