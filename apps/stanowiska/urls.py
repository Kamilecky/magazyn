from django.urls import path
from . import views

app_name = 'stanowiska'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('dodaj/', views.dodaj, name='dodaj'),
    path('<int:pk>/', views.podglad, name='podglad'),
    path('<int:pk>/edytuj/', views.edytuj, name='edytuj'),
    path('<int:pk>/usun/', views.usun, name='usun'),
]
