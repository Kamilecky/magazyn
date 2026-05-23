from django.contrib import admin
from .models import Stanowisko


@admin.register(Stanowisko)
class StanowiskoAdmin(admin.ModelAdmin):
    list_display = ['nazwa', 'wymagana_sila_kg', 'praca_stojaca', 'praca_przy_monitorze', 'wymaga_komputera', 'max_pracownikow', 'aktywne']
    list_filter = ['aktywne', 'praca_stojaca', 'praca_przy_monitorze', 'wymaga_komputera']
    search_fields = ['nazwa']
