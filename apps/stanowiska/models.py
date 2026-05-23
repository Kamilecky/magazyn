from django.db import models

POZIOM_CHOICES = [
    (1, 'Bardzo niski'),
    (2, 'Niski'),
    (3, 'Średni'),
    (4, 'Wysoki'),
    (5, 'Bardzo wysoki'),
]

DZWIGANIE_CHOICES = [
    ('0-5', '0–5 kg'),
    ('6-10', '6–10 kg'),
    ('11-15', '11–15 kg'),
    ('16-20', '16–20 kg'),
    ('>20', 'Powyżej 20 kg'),
]


class Stanowisko(models.Model):
    nazwa = models.CharField(max_length=200, verbose_name='Nazwa')
    opis = models.TextField(blank=True, verbose_name='Opis')
    wymagana_sila_kg = models.IntegerField(default=0, verbose_name='Wymagana siła (kg)')
    praca_stojaca = models.BooleanField(default=False, verbose_name='Praca stojąca')
    praca_przy_monitorze = models.BooleanField(default=False, verbose_name='Praca przy monitorze')
    wymaga_komputera = models.BooleanField(default=False, verbose_name='Wymaga komputera')
    max_pracownikow = models.IntegerField(default=1, verbose_name='Maks. pracowników')
    aktywne = models.BooleanField(default=True, verbose_name='Aktywne')
    # Pola do tooltipów
    zakres_dzwigania = models.CharField(
        max_length=10, choices=DZWIGANIE_CHOICES, default='0-5', verbose_name='Zakres dźwigania'
    )
    poziom_chodzenia = models.IntegerField(
        choices=POZIOM_CHOICES, default=3, verbose_name='Poziom chodzenia'
    )
    poziom_siedzenia = models.IntegerField(
        choices=POZIOM_CHOICES, default=3, verbose_name='Poziom siedzenia'
    )
    powtarzalnosc_czynnosci = models.IntegerField(
        choices=POZIOM_CHOICES, default=3, verbose_name='Powtarzalność czynności'
    )
    praca_na_zewnatrz = models.BooleanField(default=False, verbose_name='Praca na zewnątrz')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Utworzono')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Zaktualizowano')

    class Meta:
        verbose_name = 'Stanowisko'
        verbose_name_plural = 'Stanowiska'
        ordering = ['nazwa']

    def __str__(self):
        return self.nazwa

    def aktualna_obsada(self):
        return self.przydzia_set.filter(aktywny=True).count()
