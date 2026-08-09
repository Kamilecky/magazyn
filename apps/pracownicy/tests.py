from django.test import TestCase

from .models import (
    Aktywnosc,
    KompetencjaPracownika,
    KonfiguracjaZmian,
    PlanDzienny,
    Pracownik,
    PracownikAPT,
    ZapotrzebowanieGodzinowe,
)
from .przydzial_flow import (
    apt_pasuje_zmiana,
    dzialy_fuzzy_match,
    koszt_dopasowania,
    pasuje_zmiana,
)
from .views import _wykonaj_przydzial


# ── Testy jednostkowe (bez bazy) — semantyka P1/P2/P3 ─────────────────────────

class PasujeZmianaTestCase(TestCase):
    def test_dokladne_dopasowanie_pola_zmiana(self):
        p = Pracownik(zmiana='A', zmiana_grupa='')
        self.assertTrue(pasuje_zmiana(p, 'A'))
        self.assertFalse(pasuje_zmiana(p, 'B'))

    def test_fallback_na_pierwsza_litere_zmiana_grupa(self):
        p = Pracownik(zmiana='', zmiana_grupa='A-1')
        self.assertTrue(pasuje_zmiana(p, 'A'))
        self.assertFalse(pasuje_zmiana(p, 'B'))

    def test_pracownik_bez_zmiany_nie_pasuje_do_zadnej_litery(self):
        p = Pracownik(zmiana='', zmiana_grupa='')
        self.assertFalse(pasuje_zmiana(p, 'A'))
        self.assertFalse(pasuje_zmiana(p, 'D'))

    def test_apt_pasuje_zmiana(self):
        apt = PracownikAPT(grupa='B-2')
        self.assertTrue(apt_pasuje_zmiana(apt, 'B'))
        self.assertFalse(apt_pasuje_zmiana(apt, 'A'))
        self.assertFalse(apt_pasuje_zmiana(PracownikAPT(grupa=''), 'A'))


class DzialyFuzzyMatchTestCase(TestCase):
    def test_substring_dopasowanie(self):
        matched, ratio, metoda = dzialy_fuzzy_match('Outbound', 'Dział Outbound')
        self.assertTrue(matched)
        self.assertEqual(metoda, 'substring')

    def test_fuzzy_powyzej_progu_akceptacji(self):
        matched, ratio, metoda = dzialy_fuzzy_match('Kompletacja Retail', 'Kompletacje Retail')
        self.assertTrue(matched)
        self.assertEqual(metoda, 'fuzzy')
        self.assertGreaterEqual(ratio, 0.85)

    def test_strefa_niepewnosci_loguje_ostrzezenie_i_nie_dopasowuje(self):
        with self.assertLogs('apps.pracownicy.przydzial_flow', level='WARNING') as logi:
            matched, ratio, metoda = dzialy_fuzzy_match('Dzial Kompletacji', 'kompletacja')
        self.assertFalse(matched)
        self.assertEqual(metoda, 'review')
        self.assertTrue(0.70 <= ratio < 0.85)
        self.assertTrue(any('przeglądu ręcznego' in msg for msg in logi.output))

    def test_calkowicie_rozne_dzialy_nie_dopasowane_bez_ostrzezenia(self):
        matched, ratio, metoda = dzialy_fuzzy_match('Inbound', 'Prasa KDR')
        self.assertFalse(matched)
        self.assertEqual(metoda, 'none')


class KosztDopasowaniaTestCase(TestCase):
    def test_brak_kompetencji_nie_wywala_wyjatku_i_stosuje_domyslna_kare(self):
        koszt = koszt_dopasowania('Outbound', 'Outbound', None, {}, dept_kod_ok=False)
        self.assertTrue(koszt.brak_danych)
        self.assertEqual(koszt.kompetencja, 0.0)
        self.assertEqual(koszt.koszt, 10 + 1)  # KOSZT_MAX_KOMPETENCJI + BRAK_KOMPETENCJI_PENALTY

    def test_niezgodny_dzial_dodaje_kare_penalty_dzial(self):
        zgodny = koszt_dopasowania('Outbound', 'Outbound', 50.0, {}, dept_kod_ok=False)
        niezgodny = koszt_dopasowania('Inbound', 'Outbound', 50.0, {}, dept_kod_ok=False)
        self.assertTrue(zgodny.dzial_ok)
        self.assertFalse(niezgodny.dzial_ok)
        self.assertGreaterEqual(niezgodny.koszt - zgodny.koszt, 10_000)

    def test_dominacja_penalty_dzial_nad_calym_zakresem_kompetencji(self):
        # żadna kombinacja ocen kompetencji (0-50) nie może przebić niezgodności działu
        koszty_zgodne = [
            koszt_dopasowania('Outbound', 'Outbound', w, {}, dept_kod_ok=False).koszt
            for w in range(0, 51, 5)
        ]
        koszty_niezgodne = [
            koszt_dopasowania('Inbound', 'Outbound', w, {}, dept_kod_ok=False).koszt
            for w in range(0, 51, 5)
        ]
        self.assertLess(max(koszty_zgodne), min(koszty_niezgodne))

    def test_dept_kod_ok_wymusza_zgodnosc_dzialu_dla_apt(self):
        koszt = koszt_dopasowania('', '', 30.0, {}, dept_kod_ok=True)
        self.assertTrue(koszt.dzial_ok)


# ── Testy integracyjne — pełny przebieg _wykonaj_przydzial ────────────────────

class WykonajPrzydzialTestCase(TestCase):
    """Nazwa aktywności musi być realnym wpisem z grupy_procesowe.GRUPY_PROCESOWE,
    żeby worker_group_score (macierz procesowa, oś niezależna od P1/P2) faktycznie
    wyliczyło ocenę z KompetencjaPracownika zamiast zawsze zwracać None."""

    AKTYWNOSC_Z_GRUPY = 'RETAIL Przyjęcia kwarantanna'  # grupa nr 1, jedyna czynność w grupie

    def setUp(self):
        KonfiguracjaZmian.pobierz()  # singleton domyślny: 1->A, 2->B, 3->C, 4->D
        self.plan = PlanDzienny.objects.create(nazwa_pliku='test.xlsx')
        self.akt = Aktywnosc.objects.create(nazwa=self.AKTYWNOSC_Z_GRUPY, dzial='Outbound')

    def _zapotrzebowanie(self, akt, zmiana, liczba_osob, godzina=8):
        ZapotrzebowanieGodzinowe.objects.create(
            plan=self.plan, aktywnosc=akt, zmiana=zmiana, godzina=godzina, liczba_osob=liczba_osob,
        )

    def test_a_zgodny_dzial_wygrywa_mimo_nizszej_kompetencji(self):
        dobry_dzial = Pracownik.objects.create(
            imie='Ana', nazwisko='Zgodna', dzial='Outbound', departament='ZZ', zmiana='A',
        )
        zly_dzial = Pracownik.objects.create(
            imie='Bea', nazwisko='Niezgodna', dzial='Inbound', departament='ZZ', zmiana='A',
        )
        KompetencjaPracownika.objects.create(pracownik=zly_dzial, aktywnosc=self.akt, wynik=50)
        self._zapotrzebowanie(self.akt, zmiana=1, liczba_osob=1)  # capacity=1 — jedno miejsce

        dane = _wykonaj_przydzial(self.plan)
        przydzieleni = {w['pk'] for w in dane['1'][str(self.akt.pk)]['pracownicy']}
        self.assertEqual(przydzieleni, {dobry_dzial.pk})

    def test_b_pracownik_z_niezgodna_zmiana_nigdy_nie_pojawia_sie_w_przydziale(self):
        zla_zmiana = Pracownik.objects.create(
            imie='Cezary', nazwisko='ZlaZmiana', dzial='Outbound', departament='ZZ', zmiana='B',
        )
        KompetencjaPracownika.objects.create(pracownik=zla_zmiana, aktywnosc=self.akt, wynik=50)
        self._zapotrzebowanie(self.akt, zmiana=1, liczba_osob=1)

        dane = _wykonaj_przydzial(self.plan)
        for zmiana_klucz, zmiana_dane in dane.items():
            if zmiana_klucz == '__ostrzezenia_dzialow__':
                continue
            for akt_klucz, akt_dane in zmiana_dane.items():
                if akt_klucz == '__fillers__':
                    continue  # filler = NIE przydzielony; zla_zmiana ma tu prawo się pojawić
                pks = {w['pk'] for w in akt_dane.get('pracownicy', [])}
                self.assertNotIn(zla_zmiana.pk, pks)

    def test_d_brak_oceny_kompetencji_nie_wywala_wyjatku(self):
        pracownik = Pracownik.objects.create(
            imie='Dorota', nazwisko='BrakOceny', dzial='Outbound', departament='ZZ', zmiana='A',
        )
        self._zapotrzebowanie(self.akt, zmiana=1, liczba_osob=1)

        dane = _wykonaj_przydzial(self.plan)  # nie powinno rzucić wyjątku
        przydzieleni = {w['pk']: w for w in dane['1'][str(self.akt.pk)]['pracownicy']}
        self.assertIn(pracownik.pk, przydzieleni)
        self.assertIsNone(przydzieleni[pracownik.pk]['wynik'])

    def test_pojemnosc_jest_respektowana(self):
        for i in range(5):
            Pracownik.objects.create(
                imie=f'P{i}', nazwisko=f'Rowny{i}', dzial='Outbound', departament='ZZ', zmiana='A',
            )
        self._zapotrzebowanie(self.akt, zmiana=1, liczba_osob=2)  # capacity=2

        dane = _wykonaj_przydzial(self.plan)
        akt_dane = dane['1'][str(self.akt.pk)]
        self.assertEqual(len(akt_dane['pracownicy']), 2)
        self.assertEqual(len(dane['1']['__fillers__']['pracownicy']), 3)

    def test_nieobecny_wykluczony_mimo_idealnego_dopasowania(self):
        from .models import AbsencjaPracownika
        self.plan.data_planu = '2026-08-03'
        self.plan.save()
        pracownik = Pracownik.objects.create(
            imie='Ewa', nazwisko='Nieobecna', dzial='Outbound', departament='ZZ', zmiana='A',
        )
        KompetencjaPracownika.objects.create(pracownik=pracownik, aktywnosc=self.akt, wynik=50)
        AbsencjaPracownika.objects.create(pracownik=pracownik, data='2026-08-03', typ='L4')
        self._zapotrzebowanie(self.akt, zmiana=1, liczba_osob=1)

        dane = _wykonaj_przydzial(self.plan)
        przydzieleni = {w['pk'] for w in dane['1'][str(self.akt.pk)]['pracownicy']}
        self.assertNotIn(pracownik.pk, przydzieleni)
        fillerzy = {w['pk']: w for w in dane['1']['__fillers__']['pracownicy']}
        self.assertIn(pracownik.pk, fillerzy)
        self.assertEqual(fillerzy[pracownik.pk]['powod'], 'nieobecny')

    def test_apt_nigdy_nie_wypiera_etatowego_pracownika(self):
        from .models import KolumnaAPT, OcenaAPT
        etat = Pracownik.objects.create(
            imie='Filip', nazwisko='Etatowy', dzial='Outbound', departament='ZZ', zmiana='A',
        )
        apt = PracownikAPT.objects.create(
            imie='Grazyna', nazwisko='Agencyjna', nazwa_agencji='Agencja X', grupa='A-1',
        )
        kolumna = KolumnaAPT.objects.create(numer_kolumny=1, nazwa_dzialu='Outbound')
        OcenaAPT.objects.create(pracownik_apt=apt, numer_kolumny=kolumna.numer_kolumny, ocena=50)
        self._zapotrzebowanie(self.akt, zmiana=1, liczba_osob=1)  # capacity=1

        dane = _wykonaj_przydzial(self.plan)
        przydzieleni = dane['1'][str(self.akt.pk)]['pracownicy']
        self.assertEqual(len(przydzieleni), 1)
        self.assertEqual(przydzieleni[0]['pk'], etat.pk)
        self.assertFalse(przydzieleni[0]['apt'])

    def test_shift_d_smoke(self):
        akt_prasa = Aktywnosc.objects.create(nazwa='Prasa KDR', dzial='Prasa')
        pracownik_d = Pracownik.objects.create(
            imie='Hubert', nazwisko='ZmianaD', dzial='Prasa', departament='PR', zmiana_grupa='D-1',
        )
        self._zapotrzebowanie(akt_prasa, zmiana=1, liczba_osob=1)

        dane = _wykonaj_przydzial(self.plan)
        self.assertIn('4', dane)
        pks_d = {w['pk'] for akt in dane['4'].values() if isinstance(akt, dict)
                 for w in akt.get('pracownicy', [])}
        self.assertIn(pracownik_d.pk, pks_d)


class PrzydzialShiftComplianceTestCase(TestCase):
    """Regresja dla kryterium akceptacji: 'żadne przypisanie nie narusza zgodności zmiany'.

    Wyjątek zaprojektowany świadomie: pracownicy "bez zmiany" (puste `zmiana` I
    `zmiana_grupa`) są celowo zwolnieni z P1 i mogą wypełnić lukę w dowolnej
    zmianie 1-3 (patrz komentarz w _wykonaj_przydzial) — to nie jest naruszenie
    zgodności zmiany, tylko brak zadeklarowanej preferencji. Znaleziono to
    rozróżnienie podczas ręcznej weryfikacji na realnych danych (2 przypadki
    zgłoszone przez naiwne sprawdzenie pasuje_zmiana() okazały się być właśnie
    tym wyjątkiem, nie błędem)."""

    def test_zero_naruszen_zgodnosci_zmiany(self):
        KonfiguracjaZmian.pobierz()
        plan = PlanDzienny.objects.create(nazwa_pliku='compliance.xlsx')
        litera_map = KonfiguracjaZmian.pobierz().jako_slownik()

        akt = Aktywnosc.objects.create(nazwa='RETAIL Przyjęcia kwarantanna', dzial='Outbound')
        for litera, zmiana in (('A', 1), ('B', 2), ('C', 3)):
            for i in range(2):
                Pracownik.objects.create(
                    imie=f'{litera}{i}', nazwisko=f'Zm{litera}{i}',
                    dzial='Outbound', departament='ZZ', zmiana=litera,
                )
            ZapotrzebowanieGodzinowe.objects.create(
                plan=plan, aktywnosc=akt, zmiana=zmiana, godzina=8, liczba_osob=3,
            )
        # Pracownik "bez zmiany" — powinien móc wypełnić lukę w zmianie 1-3 (wyjątek),
        # ale NIE powinien liczyć się jako naruszenie P1.
        bez_zmiany = Pracownik.objects.create(
            imie='Iza', nazwisko='BezZmiany', dzial='Outbound', departament='ZZ',
        )

        dane = _wykonaj_przydzial(plan)
        pk_to_prac = {p.pk: p for p in Pracownik.objects.all()}
        for zmiana_klucz in ('1', '2', '3', '4'):
            if zmiana_klucz not in dane:
                continue
            litera = litera_map[int(zmiana_klucz)]
            for akt_klucz, akt_dane in dane[zmiana_klucz].items():
                if akt_klucz == '__fillers__':
                    continue
                for w in akt_dane['pracownicy']:
                    if w.get('apt'):
                        continue
                    pracownik = pk_to_prac[w['pk']]
                    ma_deklarowana_zmiane = bool(
                        (pracownik.zmiana or '').strip() or (pracownik.zmiana_grupa or '').strip()
                    )
                    if not ma_deklarowana_zmiane:
                        continue  # wyjątek "bez zmiany" — brak deklaracji, nie naruszenie
                    self.assertTrue(
                        pasuje_zmiana(pracownik, litera),
                        f"{pracownik} przydzielony do zmiany {litera}, do której nie pasuje",
                    )
