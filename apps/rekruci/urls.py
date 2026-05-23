from django.urls import path
from . import views

app_name = 'rekruci'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('orzeczenia/', views.orzeczenia_lista, name='orzeczenia'),
    path('dodaj/', views.dodaj, name='dodaj'),
    path('<int:pk>/', views.podglad, name='podglad'),
    path('<int:pk>/edytuj/', views.edytuj, name='edytuj'),
    path('<int:pk>/scoring/', views.wyniki_scoringu, name='scoring'),
    path('stanowisko/<int:pk>/json/', views.stanowisko_json, name='stanowisko_json'),
]
