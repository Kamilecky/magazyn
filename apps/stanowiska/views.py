from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Stanowisko
from .forms import StanowiskoForm
from apps.pracownicy.models import Pracownik


def _kolor(proc):
    return 'danger' if proc > 90 else ('warning' if proc >= 70 else 'success')


def _pracownicy_ze_stanowiska(stanowisko_nazwa):
    # Dawny system dopasowania (PlanZmiany) zastąpiony nowym — brak danych przydziałów.
    return []
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


@login_required
def dodaj(request):
    if request.method == 'POST':
        form = StanowiskoForm(request.POST)
        if form.is_valid():
            stanowisko = form.save()
            messages.success(request, f'Stanowisko „{stanowisko.nazwa}" zostało dodane.')
            return redirect('stanowiska:podglad', pk=stanowisko.pk)
    else:
        form = StanowiskoForm()
    return render(request, 'stanowiska/formularz.html', {'form': form, 'tryb': 'dodaj'})


@login_required
def edytuj(request, pk):
    stanowisko = get_object_or_404(Stanowisko, pk=pk)
    if request.method == 'POST':
        form = StanowiskoForm(request.POST, instance=stanowisko)
        if form.is_valid():
            form.save()
            messages.success(request, f'Stanowisko „{stanowisko.nazwa}" zostało zaktualizowane.')
            return redirect('stanowiska:podglad', pk=stanowisko.pk)
    else:
        form = StanowiskoForm(instance=stanowisko)
    return render(request, 'stanowiska/formularz.html', {'form': form, 'stanowisko': stanowisko, 'tryb': 'edycja'})


@login_required
def usun(request, pk):
    stanowisko = get_object_or_404(Stanowisko, pk=pk)
    if request.method == 'POST':
        nazwa = stanowisko.nazwa
        stanowisko.delete()
        messages.success(request, f'Stanowisko „{nazwa}" zostało usunięte.')
        return redirect('stanowiska:lista')
    return redirect('stanowiska:edytuj', pk=pk)
