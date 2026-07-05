from django.urls import path
from . import views

urlpatterns = [
    path('plan-zmianowy/', views.import_plan_zmianowy, name='import_plan_zmianowy'),
    path('pracownicy/', views.import_pracownicy, name='import_pracownicy'),
    path('pracownicy-apt/', views.import_pracownicy_apt, name='import_pracownicy_apt'),
]
