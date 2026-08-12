from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.stanowiska.models import Stanowisko
from apps.pracownicy.models import Pracownik, PlanDzienny


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
