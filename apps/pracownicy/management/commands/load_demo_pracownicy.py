from django.core.management.base import BaseCommand
from apps.pracownicy.models import Pracownik

DEMO = [
    # 1 stanowisko
    {'imie': 'Marek',     'nazwisko': 'Wójcik',       'stanowiska': ['Wózek - Retrack']},
    {'imie': 'Monika',    'nazwisko': 'Wiśniewska',   'stanowiska': ['Sorter - Zbieranie']},
    {'imie': 'Katarzyna', 'nazwisko': 'Woźniak',      'stanowiska': ['PTS 4']},
    {'imie': 'Grzegorz',  'nazwisko': 'Adamski',      'stanowiska': ['AA']},
    {'imie': 'Zofia',     'nazwisko': 'Wysocka',      'stanowiska': ['Wózek - Piesek']},
    # 2 stanowiska
    {'imie': 'Anna',      'nazwisko': 'Kowalska',     'stanowiska': ['PTS 4', 'Sorter - Wrzucanie']},
    {'imie': 'Tomasz',    'nazwisko': 'Zając',        'stanowiska': ['PTS 4', 'PTS 10']},
    {'imie': 'Rafał',     'nazwisko': 'Kowalczyk',    'stanowiska': ['AA', 'PTS 10']},
    {'imie': 'Joanna',    'nazwisko': 'Dąbrowska',    'stanowiska': ['Sorter - Wrzucanie', 'Wózek - Piesek']},
    {'imie': 'Bartosz',   'nazwisko': 'Szymański',    'stanowiska': ['Wózek - Czołówka', 'Wózek - Retrack']},
    {'imie': 'Ewa',       'nazwisko': 'Jankowska',    'stanowiska': ['Wózek - Piesek', 'AA']},
    {'imie': 'Natalia',   'nazwisko': 'Krawczyk',     'stanowiska': ['Sorter - Zbieranie', 'PTS 10']},
    # 3 stanowiska
    {'imie': 'Piotr',     'nazwisko': 'Nowak',        'stanowiska': ['PTS 10', 'Wózek - Czołówka', 'AA']},
    {'imie': 'Karolina',  'nazwisko': 'Lewandowska',  'stanowiska': ['Wózek - Piesek', 'Sorter - Wrzucanie', 'AA']},
    {'imie': 'Agnieszka', 'nazwisko': 'Kamińska',     'stanowiska': ['PTS 4', 'Sorter - Zbieranie', 'Wózek - Czołówka']},
    {'imie': 'Damian',    'nazwisko': 'Kozłowski',    'stanowiska': ['PTS 10', 'Sorter - Wrzucanie', 'Sorter - Zbieranie']},
    {'imie': 'Michał',    'nazwisko': 'Mazur',        'stanowiska': ['PTS 4', 'Wózek - Retrack', 'AA']},
]


class Command(BaseCommand):
    help = 'Ładuje demonstracyjnych pracowników z przypisanymi stanowiskami'

    def handle(self, *args, **options):
        dodano = zaktualizowano = 0
        for d in DEMO:
            _, created = Pracownik.objects.update_or_create(
                imie=d['imie'],
                nazwisko=d['nazwisko'],
                defaults={'stanowiska': d['stanowiska'], 'zrodlo': 'demo'},
            )
            if created:
                dodano += 1
            else:
                zaktualizowano += 1
        self.stdout.write(
            self.style.SUCCESS(
                f'Gotowe. Dodano: {dodano}, zaktualizowano: {zaktualizowano} pracowników.'
            )
        )
