from django.urls import path
from . import views

app_name = 'raporty'

urlpatterns = [
    path('obsada/excel/', views.obsada_excel, name='obsada_excel'),
]
