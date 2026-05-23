from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from apps.stanowiska.models import Stanowisko
from apps.rekruci.models import Rekrut
from apps.scoring.engine import ScoringEngine
from .models import Przydzia, AuditLog


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
    obsada = []
    for s in stanowiska:
        aktualnie = s.przydzia_set.filter(aktywny=True).count()
        proc = int(aktualnie / s.max_pracownikow * 100) if s.max_pracownikow else 0
        obsada.append({
            'stanowisko': s,
            'aktualnie': aktualnie,
            'proc': min(proc, 100),
            'kolor': 'danger' if proc > 90 else ('warning' if proc >= 70 else 'success'),
        })

    engine = ScoringEngine()
    rekruci_bez = Rekrut.objects.filter(aktywny=True)
    rekruci_bez = [r for r in rekruci_bez if not r.przydzia_set.filter(aktywny=True).exists()]
    rekruci_dane = []
    for r in rekruci_bez:
        wyniki = engine.score(r)
        top = next((w for w in wyniki if not w['blokady']), None)
        ostrzezenia = top['ostrzezenia'] if top else []
        rekruci_dane.append({'rekrut': r, 'top': top, 'ostrzezenia': ostrzezenia})

    return render(request, 'przydzialy/dashboard.html', {
        'obsada': obsada,
        'rekruci_dane': rekruci_dane,
    })


@login_required
def przydziel(request):
    if request.method != 'POST':
        return redirect('przydzialy:dashboard')

    rekrut_id = request.POST.get('rekrut_id')
    stanowisko_id = request.POST.get('stanowisko_id')
    score = request.POST.get('score')
    zrodlo = request.POST.get('zrodlo', 'reczny')
    uzasadnienie = request.POST.get('uzasadnienie', '')

    rekrut = get_object_or_404(Rekrut, pk=rekrut_id)
    stanowisko = get_object_or_404(Stanowisko, pk=stanowisko_id)

    if zrodlo == 'reczny' and len(uzasadnienie.strip()) < 20:
        messages.error(request, 'Uzasadnienie musi mieć co najmniej 20 znaków.')
        return redirect('przydzialy:dashboard')

    with transaction.atomic():
        rekrut.przydzia_set.filter(aktywny=True).update(aktywny=False)
        Przydzia.objects.create(
            rekrut=rekrut,
            stanowisko=stanowisko,
            autor=request.user,
            zrodlo=zrodlo,
            uzasadnienie=uzasadnienie,
            aktywny=True,
            score_w_momencie_przydzialu=int(score) if score else None,
        )
        _log(request, f'Przydzielono {rekrut} → {stanowisko} ({zrodlo})', rekrut)

    messages.success(request, f'Przydzielono {rekrut} na stanowisko: {stanowisko.nazwa}.')
    return redirect('przydzialy:dashboard')


@login_required
def historia(request):
    przydzialy = Przydzia.objects.select_related('rekrut', 'stanowisko', 'autor').order_by('-data_przydzialu')
    return render(request, 'przydzialy/historia.html', {'przydzialy': przydzialy})
