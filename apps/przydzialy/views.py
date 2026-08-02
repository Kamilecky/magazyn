from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from apps.stanowiska.models import Stanowisko
from apps.pracownicy.models import Pracownik, PlanDzienny
from .models import AuditLog


# Zapisuje zdarzenie w logu audytu (kto, co zrobił, z jakiego IP)
def _log(request, akcja, rekrut=None):
    AuditLog.objects.create(
        uzytkownik=request.user,
        akcja=akcja,
        rekrut=rekrut,
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )


# Dashboard obsady — wyświetla stanowiska z aktualną liczbą przydzielonych pracowników
# Obsada zawsze wynosi 0 (stary system PlanZmiany jest wyłączony; dane z nowego modułu pracownicy)
@login_required
def dashboard(request):
    stanowiska = Stanowisko.objects.filter(aktywne=True)
    pracownicy_count = Pracownik.objects.count()
    # Ostatni zaimportowany plan dzienny — pokazywany jako kontekst na dashboardzie
    plan = PlanDzienny.objects.order_by('-data_importu').first()

    obsada = []
    for s in stanowiska:
        obsada.append({
            'stanowisko': s,
            'aktualnie': 0,       # brak danych z nowego systemu przydziałów
            'proc': 0,
            'kolor': 'secondary',
            'pracownicy': [],
        })

    return render(request, 'przydzialy/dashboard.html', {
        'obsada': obsada,
        'pracownicy_count': pracownicy_count,
        'ostatni_plan': plan,
    })


# Historia wszystkich przydziałów — lista z paginacją posortowana od najnowszego
@login_required
def historia(request):
    from .models import Przydzia
    # select_related pobiera powiązane obiekty w jednym zapytaniu SQL (optymalizacja)
    przydzialy = Przydzia.objects.select_related('rekrut', 'stanowisko', 'autor').order_by('-data_przydzialu')
    return render(request, 'przydzialy/historia.html', {'przydzialy': przydzialy})
