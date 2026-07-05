from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pracownicy', '0010_data_planu'),
    ]

    operations = [
        migrations.CreateModel(
            name='KonfiguracjaZmian',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('zmiana_1', models.CharField(choices=[('A', 'A'), ('B', 'B'), ('C', 'C')], default='A', max_length=1, verbose_name='Zmiana I')),
                ('zmiana_2', models.CharField(choices=[('A', 'A'), ('B', 'B'), ('C', 'C')], default='B', max_length=1, verbose_name='Zmiana II')),
                ('zmiana_3', models.CharField(choices=[('A', 'A'), ('B', 'B'), ('C', 'C')], default='C', max_length=1, verbose_name='Zmiana III')),
            ],
            options={
                'verbose_name': 'Konfiguracja zmian',
            },
        ),
    ]
