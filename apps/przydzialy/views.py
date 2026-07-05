from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from apps.stanowiska.models import Stanowisko
from apps.pracownicy.models import Pracownik, PlanDzienny
from .models import AuditLog


def _log(request, akcja, rekrut=None):
    AuditLog.objects.create(
        uzytkownik=request.user,
        akcja=akcja,
        rekrut=rekrut,
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )


@login_required
def dashboard(request):
    stanowiska = Stanowisko.objects.filter(aktywne=True)
    pracownicy_count = Pracownik.objects.count()
    plan = PlanDzienny.objects.order_by('-data_importu').first()

    obsada = []
    for s in stanowiska:
        obsada.append({
            'stanowisko': s,
            'aktualnie': 0,
            'proc': 0,
            'kolor': 'secondary',
            'pracownicy': [],
        })

    return render(request, 'przydzialy/dashboard.html', {
        'obsada': obsada,
        'pracownicy_count': pracownicy_count,
        'ostatni_plan': plan,
    })


@login_required
def historia(request):
    from .models import Przydzia
    przydzialy = Przydzia.objects.select_related('rekrut', 'stanowisko', 'autor').order_by('-data_przydzialu')
    return render(request, 'przydzialy/historia.html', {'przydzialy': przydzialy})
