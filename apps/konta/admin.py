from django.contrib import admin
from .models import Profil


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ['uzytkownik', 'rola']
    list_filter = ['rola']
    search_fields = ['uzytkownik__username', 'uzytkownik__email']
