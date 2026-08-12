from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from apps.konta.decorators import wymaga_roli
from .models import Stanowisko
from .forms import StanowiskoForm


# Zwraca kolor Bootstrap dla paska obsady: danger >90%, warning 70–90%, success <70%
def _kolor(proc):
    return 'danger' if proc > 90 else ('warning' if proc >= 70 else 'success')


# Dawny system dopasowania (PlanZmiany) zastąpiony nowym — brak danych przydziałów.
def _pracownicy_ze_stanowiska(stanowisko_nazwa):
    return []


# Lista wszystkich stanowisk z aktualnym poziomem obsady i kolorem paska
@login_required
def lista(request):
    stanowiska = Stanowisko.objects.all()
    dane = []
    for s in stanowiska:
        pracownicy = _pracownicy_ze_stanowiska(s.nazwa)
        aktualnie = len(pracownicy)
        # Procent obsady — max 100%, aby nie przekraczać szerokości paska
        proc = min(int(aktualnie / s.max_pracownikow * 100) if s.max_pracownikow else 0, 100)
        dane.append({
            'stanowisko': s,
            'aktualnie': aktualnie,
            'proc': proc,
            'kolor': _kolor(proc),
        })
    return render(request, 'stanowiska/lista.html', {'dane': dane})


# Szczegóły jednego stanowiska z listą pracowników i paskiem obsady
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


# Formularz dodawania nowego stanowiska; po zapisie przekierowanie na podgląd
@wymaga_roli('admin')
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


# Formularz edycji istniejącego stanowiska — wstępnie wypełniony aktualnymi danymi
@wymaga_roli('admin')
def edytuj(request, pk):
    stanowisko = get_object_or_404(Stanowisko, pk=pk)
    if request.method == 'POST':
        form = StanowiskoForm(request.POST, instance=stanowisko)
        if form.is_valid():
            form.save()
            messages.success(request, f'Stanowisko „{stanowisko.nazwa}" zostało zaktualizowane.')
            return redirect('stanowiska:podglad', pk=stanowisko.pk)
    else:
        # GET — wczytaj formularz z aktualnymi danymi stanowiska
        form = StanowiskoForm(instance=stanowisko)
    return render(request, 'stanowiska/formularz.html', {'form': form, 'stanowisko': stanowisko, 'tryb': 'edycja'})


# Usunięcie stanowiska — tylko przez POST (GET przekierowuje na edycję, nie usuwa)
@wymaga_roli('admin')
def usun(request, pk):
    stanowisko = get_object_or_404(Stanowisko, pk=pk)
    if request.method == 'POST':
        nazwa = stanowisko.nazwa
        stanowisko.delete()
        messages.success(request, f'Stanowisko „{nazwa}" zostało usunięte.')
        return redirect('stanowiska:lista')
    # GET na URL usunięcia → bezpieczne przekierowanie na edycję zamiast usunięcia
    return redirect('stanowiska:edytuj', pk=pk)
