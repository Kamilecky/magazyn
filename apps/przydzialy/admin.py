from django.contrib import admin
from .models import Przydzia, AuditLog


@admin.register(Przydzia)
class PrzydiaAdmin(admin.ModelAdmin):
    list_display = ['rekrut', 'stanowisko', 'zrodlo', 'aktywny', 'data_przydzialu', 'autor']
    list_filter = ['aktywny', 'zrodlo']
    search_fields = ['rekrut__nazwisko', 'rekrut__imie', 'stanowisko__nazwa']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'uzytkownik', 'akcja', 'orzeczenie_dostepne', 'ip_address']
    list_filter = ['orzeczenie_dostepne']
    search_fields = ['akcja', 'uzytkownik__username']
    readonly_fields = ['timestamp', 'uzytkownik', 'akcja', 'rekrut', 'orzeczenie_dostepne', 'ip_address']
