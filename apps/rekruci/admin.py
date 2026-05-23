from django.contrib import admin
from .models import Rekrut, AnkietaFizyczna, OrzeczenieLekarski


class AnkietaInline(admin.StackedInline):
    model = AnkietaFizyczna
    extra = 0


class OrzeczenieInline(admin.StackedInline):
    model = OrzeczenieLekarski
    extra = 0


@admin.register(Rekrut)
class RekrutAdmin(admin.ModelAdmin):
    list_display = ['nazwisko', 'imie', 'data_urodzenia', 'aktywny', 'created_at']
    list_filter = ['aktywny']
    search_fields = ['nazwisko', 'imie']
    inlines = [AnkietaInline, OrzeczenieInline]


@admin.register(AnkietaFizyczna)
class AnkietaAdmin(admin.ModelAdmin):
    list_display = ['rekrut', 'max_dzwiganie_kg', 'komfort_stania', 'tempo_pracy']
    search_fields = ['rekrut__nazwisko', 'rekrut__imie']


@admin.register(OrzeczenieLekarski)
class OrzeczenieAdmin(admin.ModelAdmin):
    list_display = ['rekrut', 'data_badania', 'data_waznosci']
    search_fields = ['rekrut__nazwisko', 'rekrut__imie']
    list_filter = ['zakaz_stania', 'zakaz_pochylania']
