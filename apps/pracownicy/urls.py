from django.urls import path
from . import views

app_name = 'pracownicy'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('import/', views.import_excel, name='import_excel'),
    path('import/plan/poranny/', views.import_plan_poranny, name='import_plan_poranny'),
    path('import/plan/popobudniowy/', views.import_plan_popobudniowy, name='import_plan_popobudniowy'),
    path('import/plan/nocny/', views.import_plan_nocny, name='import_plan_nocny'),
    path('plany/', views.plany_lista, name='plany_lista'),
    path('plany/<int:pk>/dopasuj/', views.dopasuj_plan, name='dopasuj_plan'),
    path('plany/<int:pk>/dane-edycji/', views.dane_edycji_planu, name='dane_edycji_planu'),
    path('plany/<int:pk>/edytuj-dopasowanie/', views.edytuj_dopasowanie_planu, name='edytuj_dopasowanie_planu'),
    path('plany/<int:pk>/pdf/', views.eksport_planu_pdf, name='plan_pdf'),
    path('plany/<int:pk>/usun/', views.usun_plan, name='usun_plan'),
    path('plany/<int:pk>/zmien-typ/', views.zmien_typ_planu, name='zmien_typ_planu'),
    path('<int:pk>/usun/', views.usun_pracownika, name='usun_pracownika'),
    path('usun-wszystkich/', views.usun_wszystkich, name='usun_wszystkich'),
]
