from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Stanowisko
from apps.przydzialy.models import Przydzia


@login_required
def lista(request):
    stanowiska = Stanowisko.objects.all()
    dane = []
    for s in stanowiska:
        aktualnie = s.przydzia_set.filter(aktywny=True).count()
        proc = int(aktualnie / s.max_pracownikow * 100) if s.max_pracownikow else 0
        dane.append({
            'stanowisko': s,
            'aktualnie': aktualnie,
            'proc': min(proc, 100),
            'kolor': 'danger' if proc > 90 else ('warning' if proc >= 70 else 'success'),
        })
    return render(request, 'stanowiska/lista.html', {'dane': dane})


@login_required
def podglad(request, pk):
    stanowisko = get_object_or_404(Stanowisko, pk=pk)
    przydzialy = Przydzia.objects.filter(
        stanowisko=stanowisko, aktywny=True
    ).select_related('rekrut', 'autor').order_by('-data_przydzialu')
    historia = Przydzia.objects.filter(
        stanowisko=stanowisko, aktywny=False
    ).select_related('rekrut', 'autor').order_by('-data_przydzialu')[:20]
    aktualnie = przydzialy.count()
    proc = int(aktualnie / stanowisko.max_pracownikow * 100) if stanowisko.max_pracownikow else 0
    return render(request, 'stanowiska/podglad.html', {
        'stanowisko': stanowisko,
        'przydzialy': przydzialy,
        'historia': historia,
        'aktualnie': aktualnie,
        'proc': min(proc, 100),
        'kolor': 'danger' if proc > 90 else ('warning' if proc >= 70 else 'success'),
    })
