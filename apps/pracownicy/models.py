from django.db import models
from django.contrib.auth.models import User


class Pracownik(models.Model):
    imie = models.CharField(max_length=100, verbose_name='Imię')
    nazwisko = models.CharField(max_length=100, verbose_name='Nazwisko')
    doswiadczenie = models.JSONField(default=list, verbose_name='Doświadczenie')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pracownik'
        verbose_name_plural = 'Pracownicy'
        ordering = ['nazwisko', 'imie']

    def __str__(self):
        return f'{self.imie} {self.nazwisko}'

    @property
    def inicjaly(self):
        i = self.imie[0].upper() if self.imie else ''
        n = self.nazwisko[0].upper() if self.nazwisko else ''
        return f'{i}{n}'


class PlanZmiany(models.Model):
    ZMIANA_CHOICES = [
        ('poranny', 'Plan poranny (zmiana 1)'),
        ('popobudniowy', 'Plan popołudniowy (zmiana 2)'),
        ('nocny', 'Plan nocny (zmiana 3)'),
    ]

    nazwa_pliku = models.CharField(max_length=255, verbose_name='Nazwa pliku')
    zmiana = models.CharField(max_length=15, choices=ZMIANA_CHOICES, verbose_name='Zmiana')
    data_importu = models.DateTimeField(auto_now_add=True, verbose_name='Data importu')
    importowany_przez = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, verbose_name='Importowany przez'
    )
    # AI-extracted: [{stanowisko, obsada}, ...]
    dane_raw = models.JSONField(default=list, verbose_name='Wymagania obsady')
    # Matched workers: {stanowisko: [{imie, nazwisko}, ...]}
    dopasowanie = models.JSONField(default=dict, blank=True, verbose_name='Dopasowanie')
    dopasowane_at = models.DateTimeField(null=True, blank=True, verbose_name='Data dopasowania')

    class Meta:
        ordering = ['-data_importu']
        verbose_name = 'Plan zmiany'
        verbose_name_plural = 'Plany zmian'

    def __str__(self):
        return f'{self.get_zmiana_display()} — {self.nazwa_pliku} ({self.data_importu:%d.%m.%Y %H:%M})'

    @property
    def total_obsada(self):
        return sum(int(w.get('obsada') or 0) for w in (self.dane_raw or []))

    @property
    def total_dopasowanych(self):
        return sum(len(v) for v in (self.dopasowanie or {}).values())
