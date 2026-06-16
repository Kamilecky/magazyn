from django.contrib import admin
from .models import Notatka


@admin.register(Notatka)
class NotatkaAdmin(admin.ModelAdmin):
    list_display = ['tresc', 'autor', 'created_at']
    list_filter = ['autor']
    search_fields = ['tresc']
