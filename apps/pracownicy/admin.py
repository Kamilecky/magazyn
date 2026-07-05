from django.contrib import admin
from .models import (
    Aktywnosc, PlanDzienny, ZapotrzebowanieGodzinowe,
    Pracownik, KompetencjaPracownika, AbsencjaPracownika,
    PracownikAPT, KolumnaAPT, OcenaAPT,
)


@admin.register(Aktywnosc)
class AktywnoscAdmin(admin.ModelAdmin):
    list_display = ['nazwa', 'dzial']
    list_filter = ['dzial']
    search_fields = ['nazwa', 'dzial']


@admin.register(PlanDzienny)
class PlanDziennyAdmin(admin.ModelAdmin):
    list_display = ['nazwa_pliku', 'importowany_przez', 'data_importu', 'liczba_aktywnosci']
    readonly_fields = ['data_importu']

    def liczba_aktywnosci(self, obj):
        return obj.zapotrzebowania.values('aktywnosc').distinct().count()
    liczba_aktywnosci.short_description = 'Aktywności'


@admin.register(ZapotrzebowanieGodzinowe)
class ZapotrzebowanieGodzinoweAdmin(admin.ModelAdmin):
    list_display = ['plan', 'aktywnosc', 'zmiana', 'godzina', 'liczba_osob']
    list_filter = ['zmiana', 'aktywnosc__dzial']


@admin.register(Pracownik)
class PracownikAdmin(admin.ModelAdmin):
    list_display = ['nazwisko', 'imie', 'dzial', 'zmiana', 'zmiana_grupa', 'created_at']
    list_filter = ['dzial', 'zmiana']
    search_fields = ['imie', 'nazwisko', 'nr_ewidencyjny']


@admin.register(KompetencjaPracownika)
class KompetencjaPracownikaAdmin(admin.ModelAdmin):
    list_display = ['pracownik', 'aktywnosc', 'wynik']
    list_filter = ['aktywnosc__dzial']
    search_fields = ['pracownik__imie', 'pracownik__nazwisko', 'aktywnosc__nazwa']


@admin.register(AbsencjaPracownika)
class AbsencjaPracownikaAdmin(admin.ModelAdmin):
    list_display = ['pracownik', 'data', 'typ']
    list_filter = ['typ']
    search_fields = ['pracownik__imie', 'pracownik__nazwisko']


@admin.register(PracownikAPT)
class PracownikAPTAdmin(admin.ModelAdmin):
    list_display = ['nazwisko', 'imie', 'nazwa_agencji', 'plec', 'grupa']
    list_filter = ['nazwa_agencji']
    search_fields = ['imie', 'nazwisko']


@admin.register(KolumnaAPT)
class KolumnaAPTAdmin(admin.ModelAdmin):
    list_display = ['numer_kolumny', 'nazwa_dzialu']


@admin.register(OcenaAPT)
class OcenaAPTAdmin(admin.ModelAdmin):
    list_display = ['pracownik_apt', 'numer_kolumny', 'ocena']
    list_filter = ['numer_kolumny']
