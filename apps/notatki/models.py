from django.db import models
from django.contrib.auth.models import User


# Prosta notatka użytkownika wyświetlana w panelu bocznym (offcanvas)
class Notatka(models.Model):
    tresc = models.TextField(verbose_name='Treść')
    # SET_NULL — notatka zostaje po usunięciu konta autora
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Autor')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data utworzenia')

    class Meta:
        # Domyślne sortowanie: najnowsze notatki na górze
        ordering = ['-created_at']
        verbose_name = 'Notatka'
        verbose_name_plural = 'Notatki'

    def __str__(self):
        # Skrót treści jako etykieta w panelu admina
        return self.tresc[:50]
