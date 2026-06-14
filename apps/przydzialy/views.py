from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.stanowiska.models import Stanowisko
from apps.pracownicy.models import PlanZmiany
from .models import AuditLog


def _log(request, akcja, rekrut=None):
    AuditLog.objects.create(
        uzytkownik=request.user,
        akcja=akcja,
        rekrut=rekrut,
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )


def _obsada_ze_stanowiska(stanowisko_nazwa):
    aktualnie = 0
    for zmiana in ('dzienny', 'nocny'):
        plan = PlanZmiany.objects.filter(zmiana=zmiana).first()
        if plan and plan.dopasowanie:
            aktualnie += len(plan.dopasowanie.get(stanowisko_nazwa) or [])
    return aktualnie


@login_required
def dashboard(request):
    stanowiska = Stanowisko.objects.filter(aktywne=True)
    obsada = []
    for s in stanowiska:
        aktualnie = _obsada_ze_stanowiska(s.nazwa)
        proc = min(int(aktualnie / s.max_pracownikow * 100) if s.max_pracownikow else 0, 100)
        obsada.append({
            'stanowisko': s,
            'aktualnie': aktualnie,
            'proc': proc,
            'kolor': 'danger' if proc > 90 else ('warning' if proc >= 70 else 'success'),
        })
    return render(request, 'przydzialy/dashboard.html', {'obsada': obsada})


@login_required
def historia(request):
    from .models import Przydzia
    przydzialy = Przydzia.objects.select_related('rekrut', 'stanowisko', 'autor').order_by('-data_przydzialu')
    return render(request, 'przydzialy/historia.html', {'przydzialy': przydzialy})
