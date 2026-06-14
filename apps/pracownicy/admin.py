from django.contrib import admin
from .models import Pracownik, PlanZmiany


@admin.register(Pracownik)
class PracownikAdmin(admin.ModelAdmin):
    list_display = ['imie', 'nazwisko', 'doswiadczenie', 'created_at']
    search_fields = ['imie', 'nazwisko']


@admin.register(PlanZmiany)
class PlanZmianyAdmin(admin.ModelAdmin):
    list_display = ['zmiana', 'nazwa_pliku', 'importowany_przez', 'data_importu', 'liczba_wierszy']
    list_filter = ['zmiana']
    readonly_fields = ['data_importu', 'dane_raw']

    def liczba_wierszy(self, obj):
        return len(obj.dane_raw or [])
    liczba_wierszy.short_description = 'Wierszy'
