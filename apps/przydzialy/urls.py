from django.urls import path
from . import views

app_name = 'przydzialy'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('historia/', views.historia, name='historia'),
]
