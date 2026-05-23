from django.db import models
from django.contrib.auth.models import User


class Profil(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('hr', 'HR'),
        ('kierownik', 'Kierownik'),
    ]
    uzytkownik = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profil', verbose_name='Użytkownik'
    )
    rola = models.CharField(max_length=20, choices=ROLE_CHOICES, default='hr', verbose_name='Rola')

    class Meta:
        verbose_name = 'Profil'
        verbose_name_plural = 'Profile'

    def __str__(self):
        return f'{self.uzytkownik.username} ({self.get_rola_display()})'
