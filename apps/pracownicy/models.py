from django.db import models
from django.contrib.auth.models import User


# Czynność wykonywana na magazynie, np. "Batch Mezz P3/P4/P7"; unikalna para (nazwa, dział)
class Aktywnosc(models.Model):
    nazwa = models.CharField(max_length=200, verbose_name='Nazwa')
    dzial = models.CharField(max_length=100, verbose_name='Dział')

    class Meta:
        # Ta sama nazwa aktywności może istnieć w różnych działach (np. "Pakowanie" w OB i FF)
        unique_together = ('nazwa', 'dzial')
        verbose_name = 'Aktywność'
        verbose_name_plural = 'Aktywności'
        ordering = ['dzial', 'nazwa']

    def __str__(self):
        return f'{self.dzial} / {self.nazwa}'


# Nagłówek importu planu zmianowego — przechowuje metadane pliku i datę importu
class PlanDzienny(models.Model):
    nazwa_pliku = models.CharField(max_length=255, verbose_name='Nazwa pliku')
    # Data samego planu (dzień, na który plan obowiązuje), nie data importu
    data_planu = models.DateField(null=True, blank=True, verbose_name='Data planu')
    data_importu = models.DateTimeField(auto_now_add=True, verbose_name='Data importu')
    importowany_przez = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, verbose_name='Importowany przez'
    )

    class Meta:
        # Domyślne sortowanie: najnowszy plan na górze listy
        ordering = ['-data_importu']
        verbose_name = 'Plan dzienny'
        verbose_name_plural = 'Plany dzienne'

    def __str__(self):
        return f'{self.nazwa_pliku} ({self.data_importu:%d.%m.%Y %H:%M})'


# Zapotrzebowanie na pracowników dla danej aktywności, zmiany i godziny
# Jeden rekord = jeden punkt na wykresie godzinowym (24 rekordy per aktywność per zmiana)
class ZapotrzebowanieGodzinowe(models.Model):
    plan = models.ForeignKey(PlanDzienny, on_delete=models.CASCADE, related_name='zapotrzebowania')
    aktywnosc = models.ForeignKey('Aktywnosc', on_delete=models.CASCADE, related_name='zapotrzebowania')
    zmiana = models.IntegerField(choices=[(1, 'I'), (2, 'II'), (3, 'III')])
    godzina = models.IntegerField()  # 0–23 (godzina doby)
    liczba_osob = models.FloatField(default=0)
    wolumen = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('plan', 'aktywnosc', 'zmiana', 'godzina')
        ordering = ['aktywnosc', 'zmiana', 'godzina']
        verbose_name = 'Zapotrzebowanie godzinowe'
        verbose_name_plural = 'Zapotrzebowania godzinowe'

    def __str__(self):
        return f'{self.aktywnosc} zm.{self.zmiana} g.{self.godzina}: {self.liczba_osob:.1f}'


# Pracownik etatowy (Struktura) — dane osobowe i organizacyjne z importu Excel
# UWAGA: każdy import jest destruktywny — usuwa WSZYSTKICH pracowników i wstawia nowych
class Pracownik(models.Model):
    nr_ewidencyjny = models.CharField(max_length=50, null=True, blank=True, verbose_name='Nr ewidencyjny')
    imie = models.CharField(max_length=100, verbose_name='Imię')
    nazwisko = models.CharField(max_length=100, verbose_name='Nazwisko')
    departament = models.CharField(max_length=20, blank=True, verbose_name='Departament')
    stanowisko = models.CharField(max_length=100, blank=True, verbose_name='Stanowisko')
    strefa = models.CharField(max_length=50, blank=True, verbose_name='Strefa')
    dzial = models.CharField(max_length=100, blank=True, verbose_name='Dział')
    zmiana = models.CharField(max_length=5, blank=True, verbose_name='Zmiana')
    # Zmiana grupa determinuje do której zmiany (I/II/III/D) trafi pracownik podczas przydziału
    zmiana_grupa = models.CharField(max_length=10, blank=True, verbose_name='Zmiana grupa')
    przelozony = models.CharField(max_length=100, blank=True, verbose_name='Przełożony')
    komentarz = models.TextField(blank=True, verbose_name='Komentarz')
    data_zatrudnienia = models.DateField(null=True, blank=True, verbose_name='Data zatrudnienia')
    # Nazwa arkusza Excel źródłowego, np. "Struktura IB" — używana do filtrowania i badge sektora
    arkusz = models.CharField(max_length=50, blank=True, verbose_name='Arkusz źródłowy')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pracownik'
        verbose_name_plural = 'Pracownicy'
        ordering = ['nazwisko', 'imie']

    def __str__(self):
        return f'{self.imie} {self.nazwisko}'

    # Pierwsze litery imienia i nazwiska — wyświetlane jako avatar w interfejsie
    @property
    def inicjaly(self):
        i = self.imie[0].upper() if self.imie else ''
        n = self.nazwisko[0].upper() if self.nazwisko else ''
        return f'{i}{n}'


# Wynik pracownika dla konkretnej aktywności (0–50) — tylko wiersze z wynikiem > 0
# Brak wiersza oznacza wynik 0, nie brak danych
class KompetencjaPracownika(models.Model):
    pracownik = models.ForeignKey(Pracownik, on_delete=models.CASCADE, related_name='kompetencje')
    aktywnosc = models.ForeignKey(Aktywnosc, on_delete=models.CASCADE, related_name='kompetencje')
    wynik = models.FloatField(default=0, verbose_name='Wynik')

    class Meta:
        unique_together = ('pracownik', 'aktywnosc')
        verbose_name = 'Kompetencja pracownika'
        verbose_name_plural = 'Kompetencje pracowników'

    def __str__(self):
        return f'{self.pracownik} / {self.aktywnosc}: {self.wynik}'


# Nieobecność pracownika w konkretnym dniu — blokuje go podczas przydziału na ten dzień
class AbsencjaPracownika(models.Model):
    pracownik = models.ForeignKey(Pracownik, on_delete=models.CASCADE, related_name='absencje')
    data = models.DateField(verbose_name='Data')
    typ = models.CharField(max_length=50, verbose_name='Typ absencji')

    class Meta:
        # Jeden rekord absencji per pracownik per dzień
        unique_together = ('pracownik', 'data')
        verbose_name = 'Absencja pracownika'
        verbose_name_plural = 'Absencje pracowników'

    def __str__(self):
        return f'{self.pracownik} {self.data}: {self.typ}'


# Pracownik agencyjny (APT) — oddzielna tabela bo nie ma danych strukturalnych jak etatowi
class PracownikAPT(models.Model):
    nazwisko = models.CharField(max_length=100, verbose_name='Nazwisko')
    imie = models.CharField(max_length=100, verbose_name='Imię')
    nazwa_agencji = models.CharField(max_length=50, verbose_name='Agencja')
    plec = models.CharField(max_length=10, blank=True, verbose_name='Płeć')
    # Grupa determinuje zmianę APT podczas przydziału (analogicznie do zmiana_grupa u etatowych)
    grupa = models.CharField(max_length=50, blank=True, verbose_name='Grupa')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pracownik APT'
        verbose_name_plural = 'Pracownicy APT'
        ordering = ['nazwisko', 'imie']

    def __str__(self):
        return f'{self.imie} {self.nazwisko} ({self.nazwa_agencji})'


# Mapowanie numeru kolumny (1–14) z pliku APT na nazwę działu/aktywności
# Konfigurowane przez admina w widoku import_pracownicy_apt (akcja save_mapping)
class KolumnaAPT(models.Model):
    numer_kolumny = models.IntegerField(unique=True, verbose_name='Numer kolumny (1–14)')
    nazwa_dzialu = models.CharField(max_length=100, verbose_name='Nazwa działu/poddziału')

    class Meta:
        verbose_name = 'Kolumna APT'
        verbose_name_plural = 'Kolumny APT'
        ordering = ['numer_kolumny']

    def __str__(self):
        return f'{self.numer_kolumny}: {self.nazwa_dzialu}'


# Ocena pracownika APT dla konkretnej kolumny (działu) z pliku Excel
class OcenaAPT(models.Model):
    pracownik_apt = models.ForeignKey(PracownikAPT, on_delete=models.CASCADE, related_name='oceny')
    numer_kolumny = models.IntegerField(verbose_name='Numer kolumny (1–14)')
    ocena = models.FloatField(null=True, blank=True, verbose_name='Ocena')

    class Meta:
        unique_together = ('pracownik_apt', 'numer_kolumny')
        verbose_name = 'Ocena APT'
        verbose_name_plural = 'Oceny APT'

    def __str__(self):
        return f'{self.pracownik_apt} kol.{self.numer_kolumny}: {self.ocena}'


# Konfiguracja literowa zmian — mapuje numer zmiany (1/2/3/4) na literę (A/B/C/D)
# Singleton: zawsze jeden wiersz z pk=1 (używaj KonfiguracjaZmian.pobierz())
class KonfiguracjaZmian(models.Model):
    LITERA_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
    zmiana_1 = models.CharField(max_length=1, choices=LITERA_CHOICES, default='A', verbose_name='Zmiana I')
    zmiana_2 = models.CharField(max_length=1, choices=LITERA_CHOICES, default='B', verbose_name='Zmiana II')
    zmiana_3 = models.CharField(max_length=1, choices=LITERA_CHOICES, default='C', verbose_name='Zmiana III')
    zmiana_4 = models.CharField(max_length=1, choices=LITERA_CHOICES, default='D', verbose_name='Zmiana D (PRASA/KDR)')

    class Meta:
        verbose_name = 'Konfiguracja zmian'

    # Bezpieczne pobranie singletona — tworzy rekord jeśli nie istnieje
    @classmethod
    def pobierz(cls) -> 'KonfiguracjaZmian':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # Słownik {numer_zmiany: litera} używany przez algorytm przydziału
    def jako_slownik(self) -> dict:
        return {1: self.zmiana_1, 2: self.zmiana_2, 3: self.zmiana_3, 4: self.zmiana_4}


# Wynik przydziału pracowników dla konkretnego planu dziennego — przechowywany jako JSON
# Klucze JSON: zmiana (str "1"/"2"/"3"/"4") → aktywnosc_pk (str) lub "__fillers__"
class PrzydzialDzienny(models.Model):
    # Jeden plan ma co najwyżej jeden przydział (OneToOne)
    plan = models.OneToOneField(
        PlanDzienny, on_delete=models.CASCADE,
        related_name='przydzial', verbose_name='Plan'
    )
    # Cały wynik algorytmu przydziału zapisany jako JSON — nie relacja do osobnych tabel
    dane = models.JSONField(verbose_name='Dane przydziału')
    data_przydzialu = models.DateTimeField(auto_now=True, verbose_name='Data przydziału')

    class Meta:
        verbose_name = 'Przydział dzienny'
        verbose_name_plural = 'Przydziały dzienne'

    def __str__(self):
        return f'Przydział dla {self.plan}'
