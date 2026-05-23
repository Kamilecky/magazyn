from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from apps.rekruci.models import Rekrut, AnkietaFizyczna, OrzeczenieLekarski
from apps.stanowiska.models import Stanowisko
from apps.scoring.engine import ScoringEngine


def make_rekrut(username='testuser'):
    user = User.objects.create_user(username=username, password='pass')
    rekrut = Rekrut.objects.create(
        imie='Jan', nazwisko='Kowalski',
        data_urodzenia=date(1990, 1, 1),
        created_by=user
    )
    return rekrut


def make_ankieta(rekrut, **kwargs):
    defaults = dict(
        max_dzwiganie_kg=25,
        komfort_stania=3,
        umiejetnosci_komputerowe=2,
        tempo_pracy='zrownowazone',
        preferuje_ruch=False,
        preferuje_stale_miejsce=False,
        preferuje_zespol=False,
        preferuje_samodzielnie=False,
    )
    defaults.update(kwargs)
    return AnkietaFizyczna.objects.create(rekrut=rekrut, **defaults)


def make_orzeczenie(rekrut, **kwargs):
    defaults = dict(
        status='zdolny',
        max_dzwiganie_kg=None,
        zakaz_stania=False,
        zakaz_pochylania=False,
        zakaz_monitora_h=None,
        inne_ograniczenia='',
        data_badania=date.today(),
        data_waznosci=date.today() + timedelta(days=365),
        lekarz='Dr Test',
    )
    defaults.update(kwargs)
    return OrzeczenieLekarski.objects.create(rekrut=rekrut, **defaults)


def make_stanowisko(**kwargs):
    defaults = dict(
        nazwa='Test', wymagana_sila_kg=10,
        praca_stojaca=False, praca_przy_monitorze=False,
        wymaga_komputera=False, max_pracownikow=5, aktywne=True
    )
    defaults.update(kwargs)
    return Stanowisko.objects.create(**defaults)


class ScoringEngineTest(TestCase):
    def setUp(self):
        self.engine = ScoringEngine()

    def test_blokada_brak_orzeczenia(self):
        rekrut = make_rekrut('u1')
        make_ankieta(rekrut)
        stanowisko = make_stanowisko(nazwa='S1')
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertEqual(wynik['score'], 0)
        self.assertTrue(len(wynik['blokady']) > 0)

    def test_blokada_niezdolny(self):
        rekrut = make_rekrut('u2')
        make_ankieta(rekrut)
        make_orzeczenie(rekrut, status='niezdolny')
        stanowisko = make_stanowisko(nazwa='S2')
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertEqual(wynik['score'], 0)
        self.assertTrue(any('niezdolny' in b for b in wynik['blokady']))

    def test_blokada_zakaz_stania(self):
        rekrut = make_rekrut('u3')
        make_ankieta(rekrut)
        make_orzeczenie(rekrut, zakaz_stania=True)
        stanowisko = make_stanowisko(nazwa='S3', praca_stojaca=True)
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertEqual(wynik['score'], 0)

    def test_blokada_przekroczone_dzwiganie(self):
        rekrut = make_rekrut('u4')
        make_ankieta(rekrut)
        make_orzeczenie(rekrut, max_dzwiganie_kg=10)
        stanowisko = make_stanowisko(nazwa='S4', wymagana_sila_kg=25)
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertEqual(wynik['score'], 0)
        self.assertTrue(any('25 kg' in b for b in wynik['blokady']))

    def test_blokada_monitor(self):
        rekrut = make_rekrut('u5')
        make_ankieta(rekrut)
        make_orzeczenie(rekrut, zakaz_monitora_h=2)
        stanowisko = make_stanowisko(nazwa='S5', praca_przy_monitorze=True)
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertEqual(wynik['score'], 0)

    def test_pozytywny_wynik_podstawowy(self):
        rekrut = make_rekrut('u6')
        make_ankieta(rekrut, max_dzwiganie_kg=25, tempo_pracy='szybkie')
        make_orzeczenie(rekrut)
        stanowisko = make_stanowisko(nazwa='S6', wymagana_sila_kg=10)
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertGreater(wynik['score'], 0)
        self.assertEqual(len(wynik['blokady']), 0)

    def test_ostrzezenie_wygasajace_orzeczenie(self):
        rekrut = make_rekrut('u7')
        make_ankieta(rekrut)
        make_orzeczenie(rekrut, data_waznosci=date.today() + timedelta(days=15))
        stanowisko = make_stanowisko(nazwa='S7')
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertTrue(any('wygasa' in o for o in wynik['ostrzezenia']))

    def test_ostrzezenie_wiek_dzwiganie(self):
        rekrut = make_rekrut('u8')
        rekrut.data_urodzenia = date(1965, 1, 1)
        rekrut.save()
        make_ankieta(rekrut, max_dzwiganie_kg=30)
        make_orzeczenie(rekrut)
        stanowisko = make_stanowisko(nazwa='S8', wymagana_sila_kg=20)
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertTrue(any('55 lat' in o for o in wynik['ostrzezenia']))

    def test_wyniki_posortowane_malejaco(self):
        rekrut = make_rekrut('u9')
        make_ankieta(rekrut, tempo_pracy='szybkie', preferuje_samodzielnie=True)
        make_orzeczenie(rekrut)
        make_stanowisko(nazwa='SA', wymagana_sila_kg=0)
        make_stanowisko(nazwa='SB', wymagana_sila_kg=30, praca_stojaca=True)
        wyniki = self.engine.score(rekrut)
        scores = [w['score'] for w in wyniki]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_score_nie_przekracza_100(self):
        rekrut = make_rekrut('u10')
        make_ankieta(rekrut,
            max_dzwiganie_kg=30, komfort_stania=5, umiejetnosci_komputerowe=3,
            tempo_pracy='szybkie', preferuje_ruch=True, preferuje_samodzielnie=True
        )
        make_orzeczenie(rekrut)
        stanowisko = make_stanowisko(
            nazwa='MAX', wymagana_sila_kg=25, praca_stojaca=True,
            wymaga_komputera=True
        )
        wyniki = self.engine.score(rekrut)
        wynik = next(w for w in wyniki if w['stanowisko'] == stanowisko)
        self.assertLessEqual(wynik['score'], 100)
