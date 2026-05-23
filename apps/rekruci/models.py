from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField


class Rekrut(models.Model):
    imie = models.CharField(max_length=100, verbose_name='Imię')
    nazwisko = models.CharField(max_length=100, verbose_name='Nazwisko')
    data_urodzenia = models.DateField(verbose_name='Data urodzenia')
    uwagi = models.TextField(blank=True, verbose_name='Uwagi')
    aktywny = models.BooleanField(default=True, verbose_name='Aktywny')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Utworzono')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Zaktualizowano')
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='rekruci_dodani', verbose_name='Dodany przez'
    )

    class Meta:
        verbose_name = 'Rekrut'
        verbose_name_plural = 'Rekruci'
        ordering = ['nazwisko', 'imie']

    def __str__(self):
        return f'{self.nazwisko} {self.imie}'

    @property
    def wiek(self):
        today = timezone.now().date()
        born = self.data_urodzenia
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def aktualny_przydzia(self):
        return self.przydzia_set.filter(aktywny=True).select_related('stanowisko').first()


class AnkietaFizyczna(models.Model):
    DZWIGANIE_CHOICES = [
        (0, '0 kg – brak'),
        (10, '10 kg'),
        (15, '15 kg'),
        (25, '25 kg'),
        (30, '30 kg'),
    ]
    KOMFORT_STANIA_CHOICES = [(i, str(i)) for i in range(1, 6)]
    UMIEJETNOSCI_CHOICES = [
        (0, 'Brak'),
        (1, 'Podstawy'),
        (2, 'Swobodnie'),
        (3, 'Zaawansowany'),
    ]
    TEMPO_CHOICES = [
        ('wolne', 'Wolne'),
        ('zrownowazone', 'Zrównoważone'),
        ('szybkie', 'Szybkie'),
    ]

    rekrut = models.OneToOneField(
        Rekrut, on_delete=models.CASCADE, related_name='ankieta', verbose_name='Rekrut'
    )
    max_dzwiganie_kg = models.IntegerField(choices=DZWIGANIE_CHOICES, default=0, verbose_name='Maks. dźwiganie (kg)')
    komfort_stania = models.IntegerField(choices=KOMFORT_STANIA_CHOICES, default=3, verbose_name='Komfort stania (1-5)')
    umiejetnosci_komputerowe = models.IntegerField(
        choices=UMIEJETNOSCI_CHOICES, default=0, verbose_name='Umiejętności komputerowe'
    )
    tempo_pracy = models.CharField(max_length=20, choices=TEMPO_CHOICES, default='zrownowazone', verbose_name='Tempo pracy')
    preferuje_ruch = models.BooleanField(default=False, verbose_name='Preferuje ruch')
    preferuje_stale_miejsce = models.BooleanField(default=False, verbose_name='Preferuje stałe miejsce')
    preferuje_zespol = models.BooleanField(default=False, verbose_name='Preferuje pracę w zespole')
    preferuje_samodzielnie = models.BooleanField(default=False, verbose_name='Preferuje pracę samodzielną')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Utworzono')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Zaktualizowano')

    class Meta:
        verbose_name = 'Ankieta fizyczna'
        verbose_name_plural = 'Ankiety fizyczne'

    def __str__(self):
        return f'Ankieta – {self.rekrut}'


class OrzeczenieLekarski(models.Model):
    STATUS_CHOICES = [
        ('zdolny', 'Zdolny do pracy'),
        ('z_ograniczeniami', 'Zdolny z ograniczeniami'),
        ('niezdolny', 'Niezdolny do pracy'),
    ]

    rekrut = models.OneToOneField(
        Rekrut, on_delete=models.CASCADE, related_name='orzeczenie', verbose_name='Rekrut'
    )
    status = EncryptedCharField(max_length=30, verbose_name='Status zdrowotny')
    max_dzwiganie_kg = models.IntegerField(
        null=True, blank=True, verbose_name='Maks. dźwiganie (kg)', help_text='Puste = brak ograniczeń'
    )
    zakaz_stania = models.BooleanField(default=False, verbose_name='Zakaz pracy stojącej')
    zakaz_pochylania = models.BooleanField(default=False, verbose_name='Zakaz pochylania')
    zakaz_monitora_h = models.IntegerField(
        null=True, blank=True, verbose_name='Maks. godz. przy monitorze', help_text='Puste = brak ograniczeń'
    )
    inne_ograniczenia = EncryptedTextField(blank=True, verbose_name='Inne ograniczenia')
    data_badania = models.DateField(verbose_name='Data badania')
    data_waznosci = models.DateField(verbose_name='Data ważności')
    lekarz = EncryptedCharField(max_length=200, blank=True, verbose_name='Lekarz')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Utworzono')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Zaktualizowano')

    class Meta:
        verbose_name = 'Orzeczenie lekarskie'
        verbose_name_plural = 'Orzeczenia lekarskie'

    def __str__(self):
        return f'Orzeczenie – {self.rekrut}'

    def is_wazne(self):
        return self.data_waznosci >= timezone.now().date()

    def dni_do_wygasniecia(self):
        delta = self.data_waznosci - timezone.now().date()
        return delta.days
