from django.urls import path
from . import views

app_name = 'pracownicy'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('<int:pk>/usun/', views.usun_pracownika, name='usun_pracownika'),
    path('usun-wszystkich/', views.usun_wszystkich, name='usun_wszystkich'),
    path('plany/', views.plany_lista, name='plany_lista'),
    path('plany/<int:pk>/usun/', views.usun_plan, name='usun_plan'),
    path('apt/', views.lista_pracownikow_apt, name='lista_pracownikow_apt'),
    path('<int:pk>/kompetencje/', views.kompetencje_pracownika, name='kompetencje_pracownika'),
    path('plany/<int:pk>/przydziel/', views.przydziel_plan, name='przydziel_plan'),
    path('plany/<int:pk>/wyniki/', views.wyniki_przydzialu, name='wyniki_przydzialu'),
]
