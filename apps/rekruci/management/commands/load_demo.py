from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from datetime import date
from apps.konta.models import Profil
from apps.rekruci.models import Rekrut, AnkietaFizyczna, OrzeczenieLekarski


USERS = [
    {'username': 'admin', 'password': 'Admin1234!', 'first_name': 'Adam', 'last_name': 'Administrator',
     'email': 'admin@magazyn.local', 'rola': 'admin', 'is_staff': True, 'is_superuser': True},
    {'username': 'hr_user', 'password': 'Hr1234!', 'first_name': 'Anna', 'last_name': 'HR',
     'email': 'hr@magazyn.local', 'rola': 'hr', 'is_staff': False, 'is_superuser': False},
    {'username': 'kierownik', 'password': 'Kier1234!', 'first_name': 'Karol', 'last_name': 'Kierownik',
     'email': 'kierownik@magazyn.local', 'rola': 'kierownik', 'is_staff': False, 'is_superuser': False},
]

REKRUCI = [
    {
        'imie': 'Marek', 'nazwisko': 'Nowak', 'data_urodzenia': date(1988, 5, 12),
        'ankieta': {
            'max_dzwiganie_kg': 25, 'komfort_stania': 4, 'umiejetnosci_komputerowe': 1,
            'tempo_pracy': 'szybkie', 'preferuje_ruch': True, 'preferuje_stale_miejsce': False,
            'preferuje_zespol': True, 'preferuje_samodzielnie': False,
        },
        'orzeczenie': {
            'status': 'zdolny', 'max_dzwiganie_kg': None, 'zakaz_stania': False,
            'zakaz_pochylania': False, 'zakaz_monitora_h': None, 'inne_ograniczenia': '',
            'data_badania': date(2025, 1, 10), 'data_waznosci': date(2026, 1, 10), 'lekarz': 'Dr Kowalski',
        },
    },
    {
        'imie': 'Zofia', 'nazwisko': 'Wiśniewska', 'data_urodzenia': date(1995, 8, 22),
        'ankieta': {
            'max_dzwiganie_kg': 10, 'komfort_stania': 2, 'umiejetnosci_komputerowe': 3,
            'tempo_pracy': 'zrownowazone', 'preferuje_ruch': False, 'preferuje_stale_miejsce': True,
            'preferuje_zespol': False, 'preferuje_samodzielnie': True,
        },
        'orzeczenie': {
            'status': 'zdolny', 'max_dzwiganie_kg': 10, 'zakaz_stania': False,
            'zakaz_pochylania': False, 'zakaz_monitora_h': None, 'inne_ograniczenia': '',
            'data_badania': date(2025, 3, 5), 'data_waznosci': date(2026, 3, 5), 'lekarz': 'Dr Nowak',
        },
    },
    {
        'imie': 'Tadeusz', 'nazwisko': 'Kowalczyk', 'data_urodzenia': date(1968, 2, 14),
        'uwagi': 'Rekrut powyżej 55 lat, wymaga ostrożności przy cięższych pracach.',
        'ankieta': {
            'max_dzwiganie_kg': 15, 'komfort_stania': 3, 'umiejetnosci_komputerowe': 0,
            'tempo_pracy': 'wolne', 'preferuje_ruch': True, 'preferuje_stale_miejsce': False,
            'preferuje_zespol': True, 'preferuje_samodzielnie': False,
        },
        'orzeczenie': {
            'status': 'z_ograniczeniami', 'max_dzwiganie_kg': 15, 'zakaz_stania': False,
            'zakaz_pochylania': True, 'zakaz_monitora_h': 4, 'inne_ograniczenia': 'Unikać pochylania',
            'data_badania': date(2025, 2, 20), 'data_waznosci': date(2025, 6, 5), 'lekarz': 'Dr Lewandowski',
        },
    },
    {
        'imie': 'Katarzyna', 'nazwisko': 'Zając', 'data_urodzenia': date(2001, 11, 3),
        'ankieta': {
            'max_dzwiganie_kg': 10, 'komfort_stania': 5, 'umiejetnosci_komputerowe': 2,
            'tempo_pracy': 'szybkie', 'preferuje_ruch': True, 'preferuje_stale_miejsce': False,
            'preferuje_zespol': True, 'preferuje_samodzielnie': False,
        },
        'orzeczenie': {
            'status': 'zdolny', 'max_dzwiganie_kg': None, 'zakaz_stania': False,
            'zakaz_pochylania': False, 'zakaz_monitora_h': None, 'inne_ograniczenia': '',
            'data_badania': date(2025, 4, 15), 'data_waznosci': date(2026, 4, 15), 'lekarz': 'Dr Wiśniewska',
        },
    },
    {
        'imie': 'Piotr', 'nazwisko': 'Dąbrowski', 'data_urodzenia': date(1979, 7, 30),
        'ankieta': {
            'max_dzwiganie_kg': 0, 'komfort_stania': 1, 'umiejetnosci_komputerowe': 0,
            'tempo_pracy': 'wolne', 'preferuje_ruch': False, 'preferuje_stale_miejsce': True,
            'preferuje_zespol': False, 'preferuje_samodzielnie': True,
        },
        'orzeczenie': {
            'status': 'z_ograniczeniami', 'max_dzwiganie_kg': 5, 'zakaz_stania': True,
            'zakaz_pochylania': False, 'zakaz_monitora_h': None, 'inne_ograniczenia': 'Problemy z kręgosłupem',
            'data_badania': date(2025, 1, 25), 'data_waznosci': date(2026, 1, 25), 'lekarz': 'Dr Kowalski',
        },
    },
]


class Command(BaseCommand):
    help = 'Ładuje dane demo: 3 użytkowników i 5 rekrutów'

    def handle(self, *args, **options):
        with transaction.atomic():
            hr_user = None
            for u_data in USERS:
                user, created = User.objects.get_or_create(username=u_data['username'])
                if created or not user.password:
                    user.set_password(u_data['password'])
                user.first_name = u_data['first_name']
                user.last_name = u_data['last_name']
                user.email = u_data['email']
                user.is_staff = u_data['is_staff']
                user.is_superuser = u_data['is_superuser']
                user.save()
                Profil.objects.update_or_create(uzytkownik=user, defaults={'rola': u_data['rola']})
                self.stdout.write(f'  Użytkownik: {user.username} ({"nowy" if created else "aktualizacja"})')
                if u_data['rola'] == 'hr':
                    hr_user = user

            if hr_user is None:
                hr_user = User.objects.first()

            for r_data in REKRUCI:
                rekrut, created = Rekrut.objects.get_or_create(
                    imie=r_data['imie'],
                    nazwisko=r_data['nazwisko'],
                    defaults={
                        'data_urodzenia': r_data['data_urodzenia'],
                        'uwagi': r_data.get('uwagi', ''),
                        'created_by': hr_user,
                    }
                )
                if not created:
                    rekrut.data_urodzenia = r_data['data_urodzenia']
                    rekrut.uwagi = r_data.get('uwagi', '')
                    rekrut.save()

                AnkietaFizyczna.objects.update_or_create(
                    rekrut=rekrut, defaults=r_data['ankieta']
                )
                OrzeczenieLekarski.objects.update_or_create(
                    rekrut=rekrut, defaults=r_data['orzeczenie']
                )
                self.stdout.write(f'  Rekrut: {rekrut} ({"nowy" if created else "aktualizacja"})')

        self.stdout.write(self.style.SUCCESS('Dane demo załadowane pomyślnie.'))
