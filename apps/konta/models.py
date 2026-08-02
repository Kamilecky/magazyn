from django.db import models
from django.contrib.auth.models import User


# Rozszerza wbudowanego użytkownika Django o pole roli (admin/hr/kierownik)
class Profil(models.Model):
    # Trzy role: admin ma pełny dostęp, hr i kierownik mają ograniczone uprawnienia
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('hr', 'HR'),
        ('kierownik', 'Kierownik'),
    ]
    # Powiązanie 1:1 — jeden profil na jedno konto użytkownika
    uzytkownik = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profil', verbose_name='Użytkownik'
    )
    # Rola decyduje o dostępie do widoków (sprawdzana przez dekorator @wymaga_roli)
    rola = models.CharField(max_length=20, choices=ROLE_CHOICES, default='hr', verbose_name='Rola')

    class Meta:
        verbose_name = 'Profil'
        verbose_name_plural = 'Profile'

    def __str__(self):
        return f'{self.uzytkownik.username} ({self.get_rola_display()})'
