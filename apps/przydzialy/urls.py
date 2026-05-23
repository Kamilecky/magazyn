from django.urls import path
from . import views

app_name = 'przydzialy'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('przydziel/', views.przydziel, name='przydziel'),
    path('historia/', views.historia, name='historia'),
]
