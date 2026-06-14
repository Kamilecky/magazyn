from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Pracownik',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imie', models.CharField(max_length=100, verbose_name='Imię')),
                ('nazwisko', models.CharField(max_length=100, verbose_name='Nazwisko')),
                ('stanowiska', models.JSONField(default=list, verbose_name='Stanowiska')),
                ('zrodlo', models.CharField(blank=True, max_length=200, verbose_name='Źródło importu')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Pracownik',
                'verbose_name_plural': 'Pracownicy',
                'ordering': ['nazwisko', 'imie'],
            },
        ),
        migrations.AddConstraint(
            model_name='pracownik',
            constraint=models.UniqueConstraint(
                fields=['imie', 'nazwisko'],
                name='pracownik_unikalny_imie_nazwisko',
            ),
        ),
    ]
