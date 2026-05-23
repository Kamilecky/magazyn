from django.db import models
from django.contrib.auth.models import User


class Przydzia(models.Model):
    ZRODLO_CHOICES = [
        ('ai', 'AI'),
        ('reczny', 'Ręcznie'),
    ]
    rekrut = models.ForeignKey(
        'rekruci.Rekrut', on_delete=models.CASCADE, verbose_name='Rekrut'
    )
    stanowisko = models.ForeignKey(
        'stanowiska.Stanowisko', on_delete=models.CASCADE, verbose_name='Stanowisko'
    )
    data_przydzialu = models.DateTimeField(auto_now_add=True, verbose_name='Data przydziału')
    autor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='przydzialy_wydane', verbose_name='Autor'
    )
    zrodlo = models.CharField(max_length=10, choices=ZRODLO_CHOICES, default='reczny', verbose_name='Źródło')
    uzasadnienie = models.TextField(blank=True, verbose_name='Uzasadnienie')
    aktywny = models.BooleanField(default=True, verbose_name='Aktywny')
    score_w_momencie_przydzialu = models.IntegerField(null=True, blank=True, verbose_name='Score w momencie przydziału')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Utworzono')

    class Meta:
        verbose_name = 'Przydział'
        verbose_name_plural = 'Przydziały'
        ordering = ['-data_przydzialu']

    def __str__(self):
        return f'{self.rekrut} → {self.stanowisko} ({self.get_zrodlo_display()})'


class AuditLog(models.Model):
    uzytkownik = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Użytkownik'
    )
    akcja = models.CharField(max_length=200, verbose_name='Akcja')
    rekrut = models.ForeignKey(
        'rekruci.Rekrut', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Rekrut'
    )
    orzeczenie_dostepne = models.BooleanField(default=False, verbose_name='Orzeczenie dostępne')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Czas')
    ip_address = models.CharField(max_length=50, blank=True, verbose_name='Adres IP')

    class Meta:
        verbose_name = 'Log audytu'
        verbose_name_plural = 'Logi audytu'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M} – {self.akcja}'
