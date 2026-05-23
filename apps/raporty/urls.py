from django.urls import path
from . import views

app_name = 'raporty'

urlpatterns = [
    path('rekrut/<int:pk>/pdf/', views.karta_pdf, name='karta_pdf'),
    path('obsada/excel/', views.obsada_excel, name='obsada_excel'),
    path('ostrzezenia/', views.ostrzezenia, name='ostrzezenia'),
]
