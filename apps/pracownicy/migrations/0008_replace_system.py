from django.db import migrations, models
import django.db.models.deletion


def clear_old_data(apps, schema_editor):
    Pracownik = apps.get_model('pracownicy', 'Pracownik')
    PlanZmiany = apps.get_model('pracownicy', 'PlanZmiany')
    Pracownik.objects.all().delete()
    PlanZmiany.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pracownicy', '0007_alter_planzmiany_zmiana'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # 1. Clear data before schema changes
        migrations.RunPython(clear_old_data, migrations.RunPython.noop),

        # 2. Alter Pracownik: remove old field, add new fields
        migrations.RemoveField(
            model_name='pracownik',
            name='doswiadczenie',
        ),
        migrations.AddField(
            model_name='pracownik',
            name='nr_ewidencyjny',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Nr ewidencyjny'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='departament',
            field=models.CharField(blank=True, max_length=20, verbose_name='Departament'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='stanowisko',
            field=models.CharField(blank=True, max_length=100, verbose_name='Stanowisko'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='strefa',
            field=models.CharField(blank=True, max_length=50, verbose_name='Strefa'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='dzial',
            field=models.CharField(blank=True, max_length=100, verbose_name='Dział'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='zmiana',
            field=models.CharField(blank=True, max_length=5, verbose_name='Zmiana'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='zmiana_grupa',
            field=models.CharField(blank=True, max_length=10, verbose_name='Zmiana grupa'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='przelozony',
            field=models.CharField(blank=True, max_length=100, verbose_name='Przełożony'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='komentarz',
            field=models.TextField(blank=True, verbose_name='Komentarz'),
        ),
        migrations.AddField(
            model_name='pracownik',
            name='data_zatrudnienia',
            field=models.DateField(blank=True, null=True, verbose_name='Data zatrudnienia'),
        ),

        # 3. Delete PlanZmiany
        migrations.DeleteModel(name='PlanZmiany'),

        # 4. Create new models
        migrations.CreateModel(
            name='Aktywnosc',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazwa', models.CharField(max_length=200, verbose_name='Nazwa')),
                ('dzial', models.CharField(max_length=100, verbose_name='Dział')),
            ],
            options={
                'verbose_name': 'Aktywność',
                'verbose_name_plural': 'Aktywności',
                'ordering': ['dzial', 'nazwa'],
                'unique_together': {('nazwa', 'dzial')},
            },
        ),
        migrations.CreateModel(
            name='PlanDzienny',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazwa_pliku', models.CharField(max_length=255, verbose_name='Nazwa pliku')),
                ('data_importu', models.DateTimeField(auto_now_add=True, verbose_name='Data importu')),
                ('importowany_przez', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='auth.user', verbose_name='Importowany przez'
                )),
            ],
            options={
                'verbose_name': 'Plan dzienny',
                'verbose_name_plural': 'Plany dzienne',
                'ordering': ['-data_importu'],
            },
        ),
        migrations.CreateModel(
            name='ZapotrzebowanieGodzinowe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('zmiana', models.IntegerField(choices=[(1, 'I'), (2, 'II'), (3, 'III')])),
                ('godzina', models.IntegerField()),
                ('liczba_osob', models.FloatField(default=0)),
                ('wolumen', models.FloatField(blank=True, null=True)),
                ('aktywnosc', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='zapotrzebowania', to='pracownicy.aktywnosc'
                )),
                ('plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='zapotrzebowania', to='pracownicy.plandzienny'
                )),
            ],
            options={
                'verbose_name': 'Zapotrzebowanie godzinowe',
                'verbose_name_plural': 'Zapotrzebowania godzinowe',
                'ordering': ['aktywnosc', 'zmiana', 'godzina'],
                'unique_together': {('plan', 'aktywnosc', 'zmiana', 'godzina')},
            },
        ),
        migrations.CreateModel(
            name='KompetencjaPracownika',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wynik', models.FloatField(default=0, verbose_name='Wynik')),
                ('aktywnosc', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kompetencje', to='pracownicy.aktywnosc'
                )),
                ('pracownik', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kompetencje', to='pracownicy.pracownik'
                )),
            ],
            options={
                'verbose_name': 'Kompetencja pracownika',
                'verbose_name_plural': 'Kompetencje pracowników',
                'unique_together': {('pracownik', 'aktywnosc')},
            },
        ),
        migrations.CreateModel(
            name='AbsencjaPracownika',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(verbose_name='Data')),
                ('typ', models.CharField(max_length=50, verbose_name='Typ absencji')),
                ('pracownik', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='absencje', to='pracownicy.pracownik'
                )),
            ],
            options={
                'verbose_name': 'Absencja pracownika',
                'verbose_name_plural': 'Absencje pracowników',
                'unique_together': {('pracownik', 'data')},
            },
        ),
        migrations.CreateModel(
            name='PracownikAPT',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazwisko', models.CharField(max_length=100, verbose_name='Nazwisko')),
                ('imie', models.CharField(max_length=100, verbose_name='Imię')),
                ('nazwa_agencji', models.CharField(max_length=50, verbose_name='Agencja')),
                ('plec', models.CharField(blank=True, max_length=10, verbose_name='Płeć')),
                ('grupa', models.CharField(blank=True, max_length=50, verbose_name='Grupa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Pracownik APT',
                'verbose_name_plural': 'Pracownicy APT',
                'ordering': ['nazwisko', 'imie'],
            },
        ),
        migrations.CreateModel(
            name='KolumnaAPT',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numer_kolumny', models.IntegerField(unique=True, verbose_name='Numer kolumny (1–14)')),
                ('nazwa_dzialu', models.CharField(max_length=100, verbose_name='Nazwa działu/poddziału')),
            ],
            options={
                'verbose_name': 'Kolumna APT',
                'verbose_name_plural': 'Kolumny APT',
                'ordering': ['numer_kolumny'],
            },
        ),
        migrations.CreateModel(
            name='OcenaAPT',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numer_kolumny', models.IntegerField(verbose_name='Numer kolumny (1–14)')),
                ('ocena', models.FloatField(blank=True, null=True, verbose_name='Ocena')),
                ('pracownik_apt', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='oceny', to='pracownicy.pracownikapt'
                )),
            ],
            options={
                'verbose_name': 'Ocena APT',
                'verbose_name_plural': 'Oceny APT',
                'unique_together': {('pracownik_apt', 'numer_kolumny')},
            },
        ),
    ]
