from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pracownicy', '0011_konfiguracja_zmian'),
    ]

    operations = [
        migrations.AddField(
            model_name='pracownik',
            name='arkusz',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Arkusz źródłowy'),
            preserve_default=False,
        ),
    ]
