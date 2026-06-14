from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Stanowisko
from apps.pracownicy.models import PlanZmiany


def _kolor(proc):
    return 'danger' if proc > 90 else ('warning' if proc >= 70 else 'success')


def _pracownicy_ze_stanowiska(stanowisko_nazwa):
    """Zwraca listę pracowników dopasowanych do stanowiska z najnowszych planów."""
    wyniki = []
    for zmiana in ('dzienny', 'nocny'):
        plan = PlanZmiany.objects.filter(zmiana=zmiana).first()
        if not plan or not plan.dopasowanie:
            continue
        for p in (plan.dopasowanie.get(stanowisko_nazwa) or []):
            wyniki.append({
                'imie': p.get('imie', ''),
                'nazwisko': p.get('nazwisko', ''),
                'zmiana': plan.get_zmiana_display(),
                'dopasowane_at': plan.dopasowane_at,
            })
    wyniki.sort(key=lambda r: (r['nazwisko'], r['imie']))
    return wyniki


@login_required
def lista(request):
    stanowiska = Stanowisko.objects.all()
    dane = []
    for s in stanowiska:
        pracownicy = _pracownicy_ze_stanowiska(s.nazwa)
        aktualnie = len(pracownicy)
        proc = min(int(aktualnie / s.max_pracownikow * 100) if s.max_pracownikow else 0, 100)
        dane.append({
            'stanowisko': s,
            'aktualnie': aktualnie,
            'proc': proc,
            'kolor': _kolor(proc),
        })
    return render(request, 'stanowiska/lista.html', {'dane': dane})


@login_required
def podglad(request, pk):
    stanowisko = get_object_or_404(Stanowisko, pk=pk)
    pracownicy_na_stanowisku = _pracownicy_ze_stanowiska(stanowisko.nazwa)
    aktualnie = len(pracownicy_na_stanowisku)
    proc = min(int(aktualnie / stanowisko.max_pracownikow * 100) if stanowisko.max_pracownikow else 0, 100)
    return render(request, 'stanowiska/podglad.html', {
        'stanowisko': stanowisko,
        'pracownicy_na_stanowisku': pracownicy_na_stanowisku,
        'aktualnie': aktualnie,
        'proc': proc,
        'kolor': _kolor(proc),
    })
