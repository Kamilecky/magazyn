from django.urls import path
from . import views

app_name = 'stanowiska'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('<int:pk>/', views.podglad, name='podglad'),
]
