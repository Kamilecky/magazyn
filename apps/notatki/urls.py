from django.urls import path
from . import views

app_name = 'notatki'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('dodaj/', views.dodaj, name='dodaj'),
    path('<int:pk>/usun/', views.usun, name='usun'),
]
