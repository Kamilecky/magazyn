from django.db import models
from django.contrib.auth.models import User


class Notatka(models.Model):
    tresc = models.TextField(verbose_name='Treść')
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Autor')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data utworzenia')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notatka'
        verbose_name_plural = 'Notatki'

    def __str__(self):
        return self.tresc[:50]
