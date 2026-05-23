from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from .models import Rekrut, AnkietaFizyczna, OrzeczenieLekarski
from apps.przydzialy.models import AuditLog
from apps.stanowiska.models import Stanowisko
from apps.scoring.engine import ScoringEngine


def _log(request, akcja, rekrut=None, orzeczenie_dostepne=False):
    ip = request.META.get('REMOTE_ADDR', '')
    AuditLog.objects.create(
        uzytkownik=request.user,
        akcja=akcja,
        rekrut=rekrut,
        orzeczenie_dostepne=orzeczenie_dostepne,
        ip_address=ip,
    )


@login_required
def lista(request):
    q = request.GET.get('q', '').strip()
    filtr = request.GET.get('filtr', 'wszyscy')

    rekruci_qs = (
        Rekrut.objects
        .filter(aktywny=True)
        .select_related('orzeczenie', 'ankieta')
        .prefetch_related('przydzia_set__stanowisko')
    )
    if q:
        rekruci_qs = rekruci_qs.filter(nazwisko__icontains=q) | rekruci_qs.filter(imie__icontains=q)
        rekruci_qs = rekruci_qs.filter(aktywny=True)

    engine = ScoringEngine()
    wszystkie_stanowiska = list(Stanowisko.objects.filter(aktywne=True))

    karty = []
    for r in rekruci_qs:
        if filtr == 'bez_przydzialu' and r.przydzia_set.filter(aktywny=True).exists():
            continue

        wyniki = engine.score(r)
        wyniki_dict = {w['stanowisko'].pk: w for w in wyniki}

        stanowiska_karty = []
        for s in wszystkie_stanowiska:
            w = wyniki_dict.get(s.pk, {'score': 0, 'blokady': [], 'ostrzezenia': []})
            stanowiska_karty.append({
                'stanowisko': s,
                'score': w['score'],
                'blokady': w['blokady'],
                'ostrzezenia': w['ostrzezenia'],
            })
        stanowiska_karty.sort(key=lambda x: x['score'], reverse=True)

        top_score = stanowiska_karty[0]['score'] if stanowiska_karty else 0
        aktywny = r.przydzia_set.filter(aktywny=True).select_related('stanowisko').first()
        dzial = getattr(r, 'dzial', '')

        karty.append({
            'rekrut': r,
            'stanowiska': stanowiska_karty,
            'top_score': top_score,
            'aktywny_przydzia': aktywny,
        })

    return render(request, 'rekruci/lista.html', {
        'karty': karty,
        'q': q,
        'filtr': filtr,
    })


@login_required
def stanowisko_json(request, pk):
    s = get_object_or_404(Stanowisko, pk=pk)
    return JsonResponse({
        'nazwa': s.nazwa,
        'zakres_dzwigania': s.get_zakres_dzwigania_display(),
        'poziom_chodzenia': s.get_poziom_chodzenia_display(),
        'poziom_siedzenia': s.get_poziom_siedzenia_display(),
        'powtarzalnosc': s.get_powtarzalnosc_czynnosci_display(),
        'praca_na_zewnatrz': 'Tak' if s.praca_na_zewnatrz else 'Nie',
        'wymagana_sila_kg': s.wymagana_sila_kg,
        'praca_stojaca': 'Tak' if s.praca_stojaca else 'Nie',
        'wymaga_komputera': 'Tak' if s.wymaga_komputera else 'Nie',
    })


@login_required
def dodaj(request):
    if request.method == 'POST':
        return _zapisz_rekruta(request, None)
    return render(request, 'rekruci/formularz.html', {'rekrut': None})


@login_required
def edytuj(request, pk):
    rekrut = get_object_or_404(Rekrut, pk=pk)
    if request.method == 'POST':
        return _zapisz_rekruta(request, rekrut)
    return render(request, 'rekruci/formularz.html', {'rekrut': rekrut})


def _zapisz_rekruta(request, rekrut):
    p = request.POST
    errors = []

    imie = p.get('imie', '').strip()
    nazwisko = p.get('nazwisko', '').strip()
    data_urodzenia = p.get('data_urodzenia', '').strip()
    uwagi = p.get('uwagi', '').strip()

    if not imie:
        errors.append('Imię jest wymagane.')
    if not nazwisko:
        errors.append('Nazwisko jest wymagane.')
    if not data_urodzenia:
        errors.append('Data urodzenia jest wymagana.')

    if errors:
        for e in errors:
            messages.error(request, e)
        return render(request, 'rekruci/formularz.html', {'rekrut': rekrut, 'post': p})

    try:
        with transaction.atomic():
            if rekrut is None:
                rekrut = Rekrut(created_by=request.user)
            rekrut.imie = imie
            rekrut.nazwisko = nazwisko
            rekrut.data_urodzenia = data_urodzenia
            rekrut.uwagi = uwagi
            rekrut.save()

            ankieta, _ = AnkietaFizyczna.objects.get_or_create(rekrut=rekrut)
            ankieta.max_dzwiganie_kg = int(p.get('max_dzwiganie_kg', 0))
            ankieta.komfort_stania = int(p.get('komfort_stania', 3))
            ankieta.umiejetnosci_komputerowe = int(p.get('umiejetnosci_komputerowe', 0))
            ankieta.tempo_pracy = p.get('tempo_pracy', 'zrownowazone')
            ankieta.preferuje_ruch = 'preferuje_ruch' in p
            ankieta.preferuje_stale_miejsce = 'preferuje_stale_miejsce' in p
            ankieta.preferuje_zespol = 'preferuje_zespol' in p
            ankieta.preferuje_samodzielnie = 'preferuje_samodzielnie' in p
            ankieta.save()

            status_orz = p.get('orzeczenie_status', '').strip()
            data_badania = p.get('data_badania', '').strip()
            data_waznosci = p.get('data_waznosci', '').strip()

            if status_orz and data_badania and data_waznosci:
                orzeczenie, _ = OrzeczenieLekarski.objects.get_or_create(rekrut=rekrut)
                orzeczenie.status = status_orz
                mdz = p.get('orz_max_dzwiganie_kg', '').strip()
                orzeczenie.max_dzwiganie_kg = int(mdz) if mdz else None
                orzeczenie.zakaz_stania = 'zakaz_stania' in p
                orzeczenie.zakaz_pochylania = 'zakaz_pochylania' in p
                zm_h = p.get('zakaz_monitora_h', '').strip()
                orzeczenie.zakaz_monitora_h = int(zm_h) if zm_h else None
                orzeczenie.inne_ograniczenia = p.get('inne_ograniczenia', '')
                orzeczenie.data_badania = data_badania
                orzeczenie.data_waznosci = data_waznosci
                orzeczenie.lekarz = p.get('lekarz', '')
                orzeczenie.save()

            _log(request, f'Zapisano rekruta: {rekrut}', rekrut, bool(status_orz))

        engine = ScoringEngine()
        wyniki = engine.score(rekrut)
        messages.success(request, f'Rekrut {rekrut} został zapisany.')
        return render(request, 'rekruci/wyniki_scoringu.html', {'rekrut': rekrut, 'wyniki': wyniki})

    except Exception as e:
        messages.error(request, f'Błąd zapisu: {e}')
        return render(request, 'rekruci/formularz.html', {'rekrut': rekrut, 'post': p})


@login_required
def orzeczenia_lista(request):
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now().date()
    rekruci_qs = (
        Rekrut.objects.filter(aktywny=True)
        .select_related('orzeczenie')
        .order_by('orzeczenie__data_waznosci', 'nazwisko')
    )
    dane = []
    for r in rekruci_qs:
        try:
            orz = r.orzeczenie
            dni = orz.dni_do_wygasniecia()
            stan = 'ok' if dni > 30 else ('uwaga' if dni >= 0 else 'wygaslo')
        except Exception:
            orz = None
            dni = None
            stan = 'brak'
        dane.append({'rekrut': r, 'orzeczenie': orz, 'dni': dni, 'stan': stan})
    return render(request, 'rekruci/orzeczenia.html', {'dane': dane})


@login_required
def podglad(request, pk):
    rekrut = get_object_or_404(Rekrut, pk=pk)
    historia = rekrut.przydzia_set.select_related('stanowisko', 'autor').order_by('-data_przydzialu')
    _log(request, f'Podgląd rekruta: {rekrut}', rekrut)
    return render(request, 'rekruci/podglad.html', {'rekrut': rekrut, 'historia': historia})


@login_required
def wyniki_scoringu(request, pk):
    rekrut = get_object_or_404(Rekrut, pk=pk)
    engine = ScoringEngine()
    wyniki = engine.score(rekrut)
    return render(request, 'rekruci/wyniki_scoringu.html', {'rekrut': rekrut, 'wyniki': wyniki})
