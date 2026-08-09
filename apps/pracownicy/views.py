import json
import math
import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from apps.konta.decorators import wymaga_roli
from .validators import waliduj_plik_importu
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Exists, F, OuterRef, Prefetch, Q
from django.db.models.functions import Length
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import (
    AbsencjaPracownika,
    Aktywnosc,
    KolumnaAPT,
    KompetencjaPracownika,
    KonfiguracjaZmian,
    OcenaAPT,
    PlanDzienny,
    Pracownik,
    PracownikAPT,
    PrzydzialDzienny,
    ZapotrzebowanieGodzinowe,
)
from .parsers.kompetencje import parsuj_kompetencje
from .parsers.plan_dzienny import parsuj_plan_dzienny
from .parsers.pracownicy_apt import parsuj_pracownikow_apt
from .parsers.struktura import parsuj_strukture
from .grupy_procesowe import GRUPY_PROCESOWE as _GP
from . import przydzial_flow

# ── Fuzzy-matching aktywności → grupy procesowe (moduł globalny) ──────────────
# Kompilowane raz przy starcie serwera, nie przy każdym żądaniu
import re as _re
_ws_re = _re.compile(r'\s+')           # dopasowuje wielokrotne spacje
_paren_sp_re = _re.compile(r'\s+([)\]])') # dopasowuje spację przed ) lub ]
_punct_re = _re.compile(r'[^a-ząćęłńóśźż0-9\s]')  # dopasowuje znaki interpunkcyjne


# Normalizuje string: małe litery, pojedyncze spacje, usuwa spację przed nawiasami
def _nrm(s: str) -> str:
    return _paren_sp_re.sub(r'\1', _ws_re.sub(' ', s.strip().lower()))


# Wyciąga zbiór słów (min 3 znaki) po normalizacji i usunięciu interpunkcji
# Używane do porównania zbiorów słów zamiast dopasowania podciągu
def _words(s: str) -> set:
    return set(w for w in _punct_re.sub(' ', _nrm(s)).split() if len(w) >= 3)


# Słownik: numer_grupy → obiekt grupy procesowej (szybkie wyszukiwanie po numerze)
_GP_BY_NR: dict[int, dict] = {g['nr']: g for g in _GP}

# Słownik: nazwa_czynności → grupa procesowa (dla dokładnego dopasowania nazwy)
_akt_to_group_exact: dict[str, dict] = {c: g for g in _GP for c in g['czynnosci']}

# Ręczne mapowanie dla aktywności których fuzzy-matching nie obejmuje automatycznie
# Klucz: znormalizowana nazwa aktywności z planu, wartość: lista numerów grup procesowych
_MANUAL_MAP: dict[str, list[int]] = {
    _nrm('Konsolidacje + zasileniacC(P3/P4/P7)/R1/R2'): [11, 49],
    _nrm('Retail OUT'): [54],
    _nrm('Zwroty Retail IN'): [7, 21, 27],
    _nrm('Zwroty Retail OUT'): [22, 54],
    _nrm('Total Batch'): [9, 38, 39, 40],
    _nrm('ECOM PACK'): [52],
    _nrm('Prasa Hurty'): [24],
    _nrm('Prasa KDR'): [24, 56],
    _nrm('Prasa Przyjęcia'): [24],
    _nrm('Prasa Uzupełnienia'): [24, 56],
    _nrm('Prasa VAS'): [24, 41],
}


def _find_all_groups(akt_nazwa: str) -> list[dict]:
    """Fuzzy-match nazwy aktywności planu do grup procesowych z macierzy.

    Kolejność dopasowania (fallback chain):
    1. Dokładne dopasowanie nazwy czynności
    2. Podciąg nazwy grupy (min 3 znaki) lub podzbiór słów grupy (min 2 słowa)
    3. Podciąg nazwy czynności (min 4 znaki) lub podzbiór słów czynności
    4. Ręczna mapa _MANUAL_MAP dla znanych wyjątków
    """
    norm = _nrm(akt_nazwa)
    result: list[dict] = []
    seen_nrs: set[int] = set()

    # Krok 1: dokładne dopasowanie nazwy czynności
    exact = _akt_to_group_exact.get(akt_nazwa)
    if exact:
        return [exact]
    if len(norm) < 2:
        return result

    norm_words = _words(akt_nazwa)
    for g in _GP:
        if g['nr'] in seen_nrs:
            continue
        g_norm = _nrm(g['nazwa'])
        g_words = _words(g['nazwa'])
        # Krok 2a: podciąg nazwy grupy (np. "Batch" w "Batch Mezz P3/P4/P7")
        if len(norm) >= 3 and (norm in g_norm or g_norm in norm):
            result.append(g); seen_nrs.add(g['nr']); continue
        # Krok 2b: podzbiór słów (np. {"Sort", "PTS"} ⊆ {"Sort", "PTS", "PTL"})
        if (len(norm_words) >= 2 and len(g_words) >= 2
                and (norm_words.issubset(g_words) or g_words.issubset(norm_words))):
            result.append(g); seen_nrs.add(g['nr']); continue
        # Krok 3: sprawdź poszczególne czynności w grupie
        for c in g['czynnosci']:
            c_norm = _nrm(c)
            c_words = _words(c)
            if (len(norm) >= 4 and norm in c_norm) or (len(c_norm) >= 4 and c_norm in norm):
                result.append(g); seen_nrs.add(g['nr']); break
            if (len(norm_words) >= 2 and len(c_words) >= 2
                    and (norm_words.issubset(c_words) or c_words.issubset(norm_words))):
                result.append(g); seen_nrs.add(g['nr']); break
    # Krok 4: ręczna mapa dla przypadków których algorytm nie obsługuje
    if not result:
        for nr in _MANUAL_MAP.get(norm, []):
            mg = _GP_BY_NR.get(nr)
            if mg:
                result.append(mg)
    return result


# ── Katalog tymczasowy dla plików podglądu importu ────────────────────────────

# Zwraca ścieżkę do katalogu tmp/ i tworzy go jeśli nie istnieje
def _tmp_dir() -> Path:
    d = Path(settings.BASE_DIR) / 'tmp'
    d.mkdir(exist_ok=True)
    return d


# Oblicza zakres numerów stron do wyświetlenia w paginacji (±3 od bieżącej strony)
def _page_range(page_obj, paginator):
    current = page_obj.number
    total = paginator.num_pages
    start = max(1, current - 3)
    end = min(total, current + 3)
    return range(start, end + 1), start, end


# ── Pracownicy ─────────────────────────────────────────────────────────────────

# Kolejność zakładek arkuszy na liście pracowników
_ARKUSZ_KOLEJNOSC = [
    'Struktura IN', 'Struktura IB', 'Struktura OB', 'Struktura FF', 'Struktura ZW', 'Struktura PR',
]
# Skrótowe etykiety zakładek (wyświetlane w UI)
_ARKUSZ_SKROT = {
    'Struktura IN': 'IN', 'Struktura IB': 'IB', 'Struktura OB': 'OB',
    'Struktura FF': 'FF', 'Struktura ZW': 'ZW', 'Struktura PR': 'PR',
}


# Lista pracowników z filtrowaniem, wyszukiwaniem i paginacją (50 na stronę)
@login_required
def lista(request):
    # Parametry wyszukiwania i filtrowania z URL
    q         = request.GET.get('q', '').strip()        # szukaj po imieniu/nazwisku
    arkusz_q  = request.GET.get('arkusz', '').strip()   # filtr zakładki arkusza
    nieobecni = request.GET.get('nieobecni', '') == '1' # pokaż tylko nieobecnych
    show_etat = request.GET.get('show_etat', '') == '1' # filtr: tylko etatowi
    show_apt  = request.GET.get('show_apt',  '') == '1' # filtr: tylko APT

    # Filtry kolumnowe (zaawansowane wyszukiwanie w tabeli)
    f_nr         = request.GET.get('f_nr', '').strip()
    f_nazwisko   = request.GET.get('f_nazwisko', '').strip()
    f_imie       = request.GET.get('f_imie', '').strip()
    f_stanowisko = request.GET.get('f_stanowisko', '').strip()
    f_strefa     = request.GET.get('f_strefa', '').strip()
    f_dzial      = request.GET.get('f_dzial', '').strip()
    f_zmiana     = request.GET.get('f_zmiana', '').strip()
    f_zmiana_gr  = request.GET.get('f_zmiana_gr', '').strip()
    f_przelozony = request.GET.get('f_przelozony', '').strip()

    # Główne zapytanie z anotacjami i prefetch — zoptymalizowane aby unikać N+1 zapytań
    qs = (Pracownik.objects
          .annotate(
              liczba_kompetencji=Count('kompetencje', distinct=True),
              liczba_absencji=Count('absencje', distinct=True),
              # Długość nr_ewidencyjny do sortowania (NULL-y na końcu, potem rosnąco po długości)
              nr_len=Length('nr_ewidencyjny'),
          )
          .prefetch_related(
              # absencje_lista: wszystkie absencje pracownika pobrane w jednym zapytaniu
              Prefetch('absencje',
                       queryset=AbsencjaPracownika.objects.order_by('data'),
                       to_attr='absencje_lista'),
              # kompetencje_lista: top kompetencje posortowane malejąco po wyniku
              Prefetch('kompetencje',
                       queryset=KompetencjaPracownika.objects
                           .filter(wynik__gt=0)
                           .select_related('aktywnosc')
                           .order_by('-wynik'),
                       to_attr='kompetencje_lista'),
          )
          .order_by(
              F('nr_len').asc(nulls_last=True),
              F('nr_ewidencyjny').asc(nulls_last=True),
              'nazwisko', 'imie',
          ))

    # Filtr tekstowy: szukaj w imieniu LUB nazwisku (case-insensitive)
    if q:
        qs = qs.filter(Q(nazwisko__icontains=q) | Q(imie__icontains=q))
    if arkusz_q:
        qs = qs.filter(arkusz=arkusz_q)
    # Filtr nieobecnych: tylko pracownicy z co najmniej jedną absencją
    if nieobecni:
        qs = qs.filter(liczba_absencji__gt=0)

    # Filtry kolumnowe — każdy filtr zawęża wyniki (logiczne AND)
    if f_nr:         qs = qs.filter(nr_ewidencyjny__icontains=f_nr)
    if f_nazwisko:   qs = qs.filter(nazwisko__icontains=f_nazwisko)
    if f_imie:       qs = qs.filter(imie__icontains=f_imie)
    if f_stanowisko: qs = qs.filter(stanowisko__icontains=f_stanowisko)
    if f_strefa:     qs = qs.filter(strefa__icontains=f_strefa)
    if f_dzial:      qs = qs.filter(dzial__icontains=f_dzial)
    if f_zmiana:     qs = qs.filter(zmiana__icontains=f_zmiana)
    if f_zmiana_gr:  qs = qs.filter(zmiana_grupa__icontains=f_zmiana_gr)
    if f_przelozony: qs = qs.filter(przelozony__icontains=f_przelozony)

    # Filtr przynależności: APT mają departament zaczynający się od "APT"
    if show_etat and not show_apt:
        qs = qs.exclude(departament__iregex=r'^APT')
    elif show_apt and not show_etat:
        qs = qs.filter(departament__iregex=r'^APT')

    # Oblicz liczby pracowników per arkusz dla zakładek filtrowania
    base_qs = Pracownik.objects
    if q:
        base_qs = base_qs.filter(Q(nazwisko__icontains=q) | Q(imie__icontains=q))
    if nieobecni:
        base_qs = base_qs.annotate(la=Count('absencje', distinct=True)).filter(la__gt=0)

    arkusze_counts = {
        row['arkusz']: row['n']
        for row in base_qs.values('arkusz').annotate(n=Count('id'))
    }
    # Zbuduj listę zakładek w określonej kolejności (IB/OB/FF/ZW/PR)
    arkusze_tabs = []
    for ark in _ARKUSZ_KOLEJNOSC:
        if ark in arkusze_counts:
            arkusze_tabs.append({
                'value': ark,
                'skrot': _ARKUSZ_SKROT.get(ark, ark),
                'count': arkusze_counts[ark],
            })
    # Pozostałe arkusze (spoza standardowej kolejności) na końcu
    for ark, cnt in arkusze_counts.items():
        if ark not in _ARKUSZ_KOLEJNOSC:
            arkusze_tabs.append({'value': ark, 'skrot': ark or 'Inne', 'count': cnt})

    # Zakoduj aktualne filtry jako parametry URL — do linków paginacji
    from urllib.parse import urlencode
    col_filters = {
        'f_nr': f_nr, 'f_nazwisko': f_nazwisko, 'f_imie': f_imie,
        'f_stanowisko': f_stanowisko, 'f_strefa': f_strefa, 'f_dzial': f_dzial,
        'f_zmiana': f_zmiana, 'f_zmiana_gr': f_zmiana_gr, 'f_przelozony': f_przelozony,
    }
    _fp = {k: v for k, v in [
        ('q', q), ('arkusz', arkusz_q), ('nieobecni', '1' if nieobecni else ''),
        ('show_etat', '1' if show_etat else ''), ('show_apt', '1' if show_apt else ''),
        *col_filters.items(),
    ] if v}
    filter_params = urlencode(_fp)

    # Paginacja: 50 pracowników na stronę
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    pr, pr_start, pr_end = _page_range(page_obj, paginator)
    return render(request, 'pracownicy/lista.html', {
        'pracownicy': page_obj,
        'q': q,
        'arkusz_q': arkusz_q,
        'nieobecni': nieobecni,
        'show_etat': show_etat,
        'show_apt': show_apt,
        'filter_params': filter_params,
        'arkusze_tabs': arkusze_tabs,
        'page_range': pr,
        'pr_start': pr_start,
        'pr_end': pr_end,
        **col_filters,
        'has_col_filters': any(col_filters.values()),
    })


# API endpoint: zwraca kompetencje pracownika jako JSON (używane przez modal w UI)
@login_required
def kompetencje_pracownika(request, pk):
    p = get_object_or_404(Pracownik, pk=pk)
    komp = (
        KompetencjaPracownika.objects
        .filter(pracownik=p)
        .select_related('aktywnosc')
        .order_by('aktywnosc__dzial', 'aktywnosc__nazwa')
    )
    return JsonResponse({
        'pracownik': f'{p.imie} {p.nazwisko}',
        'kompetencje': [
            {'dzial': k.aktywnosc.dzial, 'aktywnosc': k.aktywnosc.nazwa, 'wynik': k.wynik}
            for k in komp
        ],
    })


# Usuwa pojedynczego pracownika — tylko admin; POST-only (GET jest ignorowany)
@wymaga_roli('admin')
def usun_pracownika(request, pk):
    if request.method == 'POST':
        p = get_object_or_404(Pracownik, pk=pk)
        imie, nazwisko = p.imie, p.nazwisko
        p.delete()
        messages.success(request, f'Usunięto pracownika {imie} {nazwisko}.')
    return redirect('pracownicy:lista')


# Usuwa WSZYSTKICH pracowników z bazy — operacja destruktywna, tylko admin
@wymaga_roli('admin')
def usun_wszystkich(request):
    if request.method == 'POST':
        ile = Pracownik.objects.count()
        Pracownik.objects.all().delete()
        messages.success(request, f'Usunięto {ile} pracowników.')
    return redirect('pracownicy:lista')


# ── Macierz procesowa ─────────────────────────────────────────────────────────

# Wyświetla macierz 57 grup procesowych z top-8 pracownikami i statystykami pokrycia
@login_required
def macierz_procesowa(request):
    from .grupy_procesowe import GRUPY_PROCESOWE

    # tryb='ranking' pokazuje top pracowników; tryb='mapowanie' pokazuje które czynności są w DB
    tryb = request.GET.get('tryb', 'ranking')

    # Słownik wszystkich aktywności w DB: nazwa → pk (do sprawdzenia pokrycia)
    db_aktywnosci = {a.nazwa: a.pk for a in Aktywnosc.objects.only('pk', 'nazwa')}

    wynik_grup = []
    total_czynnosci_pdf = 0
    total_matched = 0

    for g in GRUPY_PROCESOWE:
        czynnosci_pdf = g['czynnosci']
        total_czynnosci_pdf += len(czynnosci_pdf)

        matched_ids = []
        matched_names = []
        unmatched_names = []
        # Sprawdź które czynności z grupy istnieją w bazie danych
        for nazwa in czynnosci_pdf:
            pk = db_aktywnosci.get(nazwa)
            if pk:
                matched_ids.append(pk)
                matched_names.append(nazwa)
                total_matched += 1
            else:
                unmatched_names.append(nazwa)

        # Top 8 pracowników z najwyższą średnią kompetencją dla tej grupy
        top = []
        if matched_ids:
            top = list(
                KompetencjaPracownika.objects
                .filter(aktywnosc_id__in=matched_ids, wynik__gt=0)
                .values('pracownik__pk', 'pracownik__imie', 'pracownik__nazwisko',
                        'pracownik__zmiana_grupa')
                .annotate(
                    sredni_wynik=Avg('wynik'),
                    liczba_aktywnosci=Count('aktywnosc_id', distinct=True),
                )
                .order_by('-sredni_wynik')[:8]
            )

        wynik_grup.append({
            'nr': g['nr'],
            'nazwa': g['nazwa'],
            'czynnosci_pdf': czynnosci_pdf,
            'matched_names': matched_names,
            'unmatched_names': unmatched_names,
            'matched_count': len(matched_ids),
            'total_count': len(czynnosci_pdf),
            'top': top,
        })

    grupy_z_danymi = sum(1 for g in wynik_grup if g['top'])
    grupy_bez_danych = sum(1 for g in wynik_grup if not g['czynnosci_pdf'])

    return render(request, 'pracownicy/macierz_procesowa.html', {
        'grupy': wynik_grup,
        'tryb': tryb,
        'stat_grup': len(GRUPY_PROCESOWE),
        'stat_czynnosci': total_czynnosci_pdf,
        'stat_matched': total_matched,
        'stat_unmatched': total_czynnosci_pdf - total_matched,
        'stat_z_danymi': grupy_z_danymi,
        'stat_bez_def': grupy_bez_danych,
    })


# ── Plany dzienne ──────────────────────────────────────────────────────────────

# Lista wszystkich zaimportowanych planów dziennych z licznikami aktywności i rekordów
@login_required
def plany_lista(request):
    plany = (
        PlanDzienny.objects
        .annotate(
            total_aktywnosci=Count('zapotrzebowania__aktywnosc', distinct=True),
            total_rekordow=Count('zapotrzebowania'),
        )
        # select_related('przydzial') — sprawdza czy plan ma już obliczony przydział
        .select_related('przydzial')
        .order_by('-data_importu')
    )
    return render(request, 'pracownicy/plany_lista.html', {'plany': plany})


# Usuwa plan dzienny wraz z jego przydziałem — tylko admin; POST-only
@wymaga_roli('admin')
def usun_plan(request, pk):
    if request.method == 'POST':
        plan = get_object_or_404(PlanDzienny, pk=pk)
        nazwa = plan.nazwa_pliku
        plan.delete()
        messages.success(request, f'Usunięto plan: {nazwa}.')
    return redirect('pracownicy:plany_lista')


# ── Lista pracowników APT ──────────────────────────────────────────────────────

# ── Przydział pracowników do planu ────────────────────────────────────────────

# Sektory priorytetowe — ich pracownicy są force-assignowani jeśli nie zostali przydzieleni
_PRIORITY_DEPTS = frozenset({'IN', 'OB', 'FF', 'ZW', 'PR'})

# Słowa kluczowe do dopasowania kodu departamentu na nazwę działu z planu (case-insensitive)
_DEPT_KEYWORDS: dict[str, list[str]] = {
    'IN': ['in', 'ib', 'inbound', 'przej', 'odbi'],
    'OB': ['ob', 'outbound', 'ekspedy', 'wysy'],
    'FF': ['ff', 'fulfil', 'kompl'],
    'ZW': ['zw', 'zwrot', 'return'],
    'PR': ['pr', 'prasa', 'press'],
}


# Normalizacja string do porównań: małe litery, usunięcie spacji brzegowych
def _norm(s: str) -> str:
    return s.strip().lower() if s else ''


# Sprawdza czy dział pracownika pasuje do działu aktywności (dopasowanie podciągu w obu kierunkach)
def _dzialy_match(dzial_p: str, dzial_a: str) -> bool:
    a, b = _norm(dzial_p), _norm(dzial_a)
    return bool(a and b and (a in b or b in a))


# Sprawdza czy kod departamentu (IN/OB/FF/ZW/PR) odpowiada nazwie działu z planu
def _dept_matches_akt(departament: str, dzial_a: str) -> bool:
    """Dopasuj kod departamentu (IN/OB/FF/ZW/PR) do nazwy działu z planu."""
    keywords = _DEPT_KEYWORDS.get(departament.strip().upper(), [])
    z = _norm(dzial_a)
    return bool(z and any(kw in z or z.startswith(kw) for kw in keywords))


# Zwraca kod strefy dla nazwy działu z planu, lub '' jeśli brak dopasowania
def _dept_for_dzial(dzial: str) -> str:
    """Zwróć kod strefy (IN/OB/FF/ZW/PR) dla nazwy działu z planu, lub '' jeśli brak."""
    z = _norm(dzial)
    for dept, keywords in _DEPT_KEYWORDS.items():
        if any(kw in z or z.startswith(kw) for kw in keywords):
            return dept
    return ''


# Wyciąga skrót sektora z nazwy arkusza (np. "Struktura FF" → "FF")
def _sektor(arkusz: str) -> str:
    """Wyciągnij skrót sektora z nazwy arkusza, np. 'Struktura FF' → 'FF'."""
    s = arkusz.strip()
    pfx = 'struktura '
    if s.lower().startswith(pfx):
        return s[len(pfx):].strip()
    return ''


# Sprawdza czy pracownik pasuje do aktywności przez dowolne z trzech kryteriów:
# stanowisko == nazwa aktywności, dział pracownika ⊂ dział aktywności, kod departamentu pasuje
def _pasuje_do_aktywnosci(p, akt_nazwa_norm: str, akt_dzial: str) -> bool:
    """True jeśli pracownik pasuje do aktywności przez dowolne kryterium."""
    return (
        _norm(p.stanowisko) == akt_nazwa_norm
        or _dzialy_match(p.dzial, akt_dzial)
        or _dept_matches_akt(p.departament, akt_dzial)
    )


def _wykonaj_przydzial(plan: PlanDzienny) -> dict:
    """
    Algorytm przydziału pracowników do aktywności planu dziennego — NetworkX min-cost flow.

    Dla każdej (aktywność, zmiana) z planu: capacity = ceil(max godzinowego zapotrzebowania).

    Hierarchia priorytetów jest leksykograficzna, nie ważona (patrz przydzial_flow.py):
      P1 — zgodność zmiany (A/B/C/D): twardy filtr — pracownik niezgodny ze zmianą
           w ogóle nie wchodzi do grafu przepływu tego "bucketu".
      P2 — zgodność działu (fuzzy, difflib + kod departamentu): PENALTY_DZIAL dominuje
           nad całym zakresem kosztu P3, więc żadna kompetencja nie przebije złego działu.
      P3 — ocena kompetencji: różnicuje wyłącznie kandydatów już zgodnych w P1 i P2.

    `networkx.max_flow_min_cost` maksymalizuje liczbę przydzieleń PRZED minimalizacją
    kosztu — dzięki temu priorytetowi (IN/OB/FF/ZW/PR) bez dopasowania działu wciąż
    mogą zostać przydzieleni (z karą PENALTY_DZIAL), jeśli to jedyny sposób wypełnienia
    wolnego miejsca, bez osobnego "force-assign".

    Etatowi i APT rozwiązywani są w dwóch kolejnych przepływach na bucket: etat najpierw,
    APT wypełnia wyłącznie pozostałą pojemność — APT nigdy nie wypiera etatowego
    pracownika, nawet przy wyższej kompetencji (decyzja świadoma, nie ograniczenie modelu).

    Nieprzydzieleni → sekcja __fillers__ (bez przypisanej aktywności).
    """
    # 1. Wczytaj zapotrzebowanie godzinowe: (akt_pk, zmiana) → {godzina: liczba_osob}
    zap_qs = (ZapotrzebowanieGodzinowe.objects
              .filter(plan=plan)
              .select_related('aktywnosc'))

    plan_godziny: dict[tuple, dict[int, float]] = {}
    for zap in zap_qs:
        key = (zap.aktywnosc_id, zap.zmiana)
        plan_godziny.setdefault(key, {})[zap.godzina] = zap.liczba_osob

    if not plan_godziny:
        return {}

    akt_pks_in_plan = {k[0] for k in plan_godziny}
    # Cache aktywności — unikamy wielokrotnych zapytań do DB podczas iteracji
    akt_cache = {a.pk: a for a in Aktywnosc.objects.filter(pk__in=akt_pks_in_plan)}

    # 2. Pracownicy etatowi — wyklucz APT (departament zaczynający się od "APT")
    pracownicy = [
        p for p in Pracownik.objects.all()
        if not p.departament.strip().upper().startswith('APT')
    ]
    pk_to_p = {p.pk: p for p in pracownicy}

    # Zbiór PKi pracowników nieobecnych w dniu planu (blokuje ich od przydziału)
    nieobecni_pks: set[int] = set()
    if plan.data_planu:
        nieobecni_pks = set(
            AbsencjaPracownika.objects
            .filter(data=plan.data_planu)
            .values_list('pracownik_id', flat=True)
        )

    # Mapa kompetencji: pracownik_pk → zbiór pk aktywności z wynikiem > 0
    komp_map: dict[int, set[int]] = {}
    for k in KompetencjaPracownika.objects.filter(aktywnosc_id__in=akt_pks_in_plan, wynik__gt=0):
        komp_map.setdefault(k.pracownik_id, set()).add(k.aktywnosc_id)

    # --- Oblicz oceny pracowników przez macierz procesową ---
    # Dla każdej aktywności z planu: fuzzy-match do grup procesowych
    # worker_group_score[(worker_pk, plan_akt_pk)] = średnia ocena pracownika przez grupę
    _nazwa_to_pk = {a.nazwa: a.pk for a in Aktywnosc.objects.only('pk', 'nazwa')}
    akt_grupa_pks: dict[int, set[int]] = {}
    for akt_pk in akt_pks_in_plan:
        akt = akt_cache[akt_pk]
        groups = _find_all_groups(akt.nazwa)
        # Zbierz PKi wszystkich czynności z dopasowanych grup procesowych
        group_czynnosci = [c for g in groups for c in g['czynnosci']]
        akt_grupa_pks[akt_pk] = {_nazwa_to_pk[n] for n in group_czynnosci if n in _nazwa_to_pk}

    all_group_pks = set()
    for pks in akt_grupa_pks.values():
        all_group_pks.update(pks)

    worker_group_score: dict[tuple, float] = {}
    if all_group_pks:
        from django.db.models import Avg as _Avg
        rows = (KompetencjaPracownika.objects
                .filter(aktywnosc_id__in=all_group_pks, wynik__gt=0)
                .values('pracownik_id', 'aktywnosc_id')
                .annotate(avg=_Avg('wynik')))
        # Odwrotny indeks: aktywnosc_pk → zbiór plan_akt_pks które ją zawierają
        group_pk_to_plan_akt: dict[int, set[int]] = {}
        for plan_akt_pk, group_pks in akt_grupa_pks.items():
            for gpk in group_pks:
                group_pk_to_plan_akt.setdefault(gpk, set()).add(plan_akt_pk)
        # Akumuluj sumy i liczby do obliczenia średniej per (worker, plan_akt)
        _sums: dict[tuple, float] = {}
        _cnts: dict[tuple, int] = {}
        for row in rows:
            wpk = row['pracownik_id']
            apk = row['aktywnosc_id']
            avg = float(row['avg'])
            for plan_akt_pk in group_pk_to_plan_akt.get(apk, set()):
                key = (wpk, plan_akt_pk)
                _sums[key] = _sums.get(key, 0.0) + avg
                _cnts[key] = _cnts.get(key, 0) + 1
        for key, s in _sums.items():
            worker_group_score[key] = s / _cnts[key]

    # 3. Pracownicy APT + mapowanie ocen na aktywności przez KolumnaAPT
    apt_pracownicy = list(PracownikAPT.objects.prefetch_related('oceny'))
    kolumna_map = {k.numer_kolumny: k.nazwa_dzialu for k in KolumnaAPT.objects.all()}
    akt_by_norm_nazwa = {_norm(a.nazwa): a for a in akt_cache.values()}

    # comp_apt[(apt_pk, akt_pk)] = najwyższa ocena APT dla tej aktywności
    comp_apt: dict[tuple, float] = {}
    for apt in apt_pracownicy:
        for ocena in apt.oceny.all():
            if ocena.ocena is None or ocena.ocena <= 0:
                continue
            nazwa_dzialu = kolumna_map.get(ocena.numer_kolumny, '')
            if not nazwa_dzialu:
                continue
            # Dopasuj nazwę działu z kolumny APT do aktywności z planu
            matched = akt_by_norm_nazwa.get(_norm(nazwa_dzialu))
            if not matched:
                for a in akt_cache.values():
                    if _dzialy_match(nazwa_dzialu, a.dzial):
                        matched = a
                        break
            if matched and matched.pk in akt_pks_in_plan:
                key = (apt.pk, matched.pk)
                comp_apt[key] = max(comp_apt.get(key, 0.0), float(ocena.ocena))
    apt_pk_to_p = {apt.pk: apt for apt in apt_pracownicy}

    # Crosswalk fuzzy dopasowania działów (P2) — budowany raz na cały przebieg, nie per para
    pary_dzialow = {(p.dzial, a.dzial) for p in pracownicy for a in akt_cache.values()}
    crosswalk, ostrzezenia_dzialow = przydzial_flow.buduj_crosswalk_dzialow(pary_dzialow)

    # Koszt krawędzi pracownik etatowy→aktywność (P2 fuzzy/departament + P3 kompetencja)
    def _koszt_etat(w, a):
        p = pk_to_p[w['key']]
        akt = akt_cache[a['pk']]
        wynik = worker_group_score.get((p.pk, a['pk']))
        dept_kod_ok = _dept_matches_akt(p.departament, akt.dzial)
        return przydzial_flow.koszt_dopasowania(p.dzial, akt.dzial, wynik, crosswalk, dept_kod_ok=dept_kod_ok)

    # Koszt krawędzi pracownik APT→aktywność — APT nie mają pola `dzial` w danych
    # źródłowych, więc kosztuje się ich wyłącznie kompetencją (dept_kod_ok wymuszone)
    def _koszt_apt(w, a):
        apt = apt_pk_to_p[w['key']]
        wynik = comp_apt.get((apt.pk, a['pk']))
        return przydzial_flow.koszt_dopasowania('', '', wynik, crosswalk, dept_kod_ok=True)

    # Buduje wpis wyniku dla jednego przydzielonego pracownika (etat lub APT),
    # ujednolicone pola niezależnie od źródła + nowe pola audytowe P2/P3
    def _worker_dict(pk, obj, koszt, apt) -> dict:
        return {
            'pk': pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
            'zmiana_grupa': obj.grupa if apt else obj.zmiana_grupa,
            'nieobecny': False,
            'wynik': round(koszt.kompetencja, 1) if not koszt.brak_danych else None,
            'zapychacz': False, 'apt': apt,
            # Pola audytowe (P2/P3) — pozwalają odróżnić dopasowanie idealne od awaryjnego
            'dzial_ok': koszt.dzial_ok,
            'fuzzy_score': round(koszt.fuzzy_score, 2),
            'kompetencja_uzyta': round(koszt.kompetencja, 1),
        }

    def _rozwiaz_bucket(eligible_etat_pks, eligible_apt_pks, shift_acts):
        """Rozwiązuje jeden bucket zmiany jako DWA kolejne przepływy min-cost:
        etat najpierw (P1/P2/P3), APT wypełnia wyłącznie pozostałą pojemność —
        APT nigdy nie wypiera etatowego pracownika (decyzja świadoma, patrz plan)."""
        activities_spec = [{'pk': akt_pk, 'capacity': cap} for akt_pk, cap, _ in shift_acts]
        # Słownik wynikowy inicjalizowany pustymi listami dla KAŻDEJ aktywności bucketu —
        # nawet tej, która ostatecznie nie dostanie nikogo (musi mieć klucz w wyniku).
        akt_assignments: dict[int, list[dict]] = {akt_pk: [] for akt_pk, _, _ in shift_acts}

        # --- Runda 1: etatowi konkurują między sobą na pełnej pojemności każdej aktywności ---
        etat_spec = [{'key': pk} for pk in eligible_etat_pks]
        etat_wynik = przydzial_flow.rozwiaz_zmiane(etat_spec, activities_spec, _koszt_etat)
        uzyci_etat: set[int] = set()
        for akt_pk in akt_assignments:
            for pk, koszt in etat_wynik.get(akt_pk, []):
                akt_assignments[akt_pk].append(_worker_dict(pk, pk_to_p[pk], koszt, apt=False))
                uzyci_etat.add(pk)

        # --- Runda 2: APT dostaje tylko to, czego etatowi nie zajęli (pojemność resztkowa) ---
        # Osobne, następujące po sobie wywołanie rozwiaz_zmiane — nie jeden wspólny graf —
        # to właśnie gwarantuje "etat zawsze przed APT": APT fizycznie nie widzi capacity,
        # które etatowi już skonsumowali, więc nie może z nimi konkurować o te same miejsca.
        residual_spec = [
            {'pk': akt_pk, 'capacity': cap - len(akt_assignments[akt_pk])}
            for akt_pk, cap, _ in shift_acts
        ]
        apt_spec = [{'key': pk} for pk in eligible_apt_pks]
        apt_wynik = przydzial_flow.rozwiaz_zmiane(apt_spec, residual_spec, _koszt_apt)
        uzyci_apt: set[int] = set()
        for akt_pk in akt_assignments:
            for pk, koszt in apt_wynik.get(akt_pk, []):
                akt_assignments[akt_pk].append(_worker_dict(pk, apt_pk_to_p[pk], koszt, apt=True))
                uzyci_apt.add(pk)

        # Sortowanie tylko kosmetyczne (wyświetlanie) — kolejność w liście nie wpływa
        # na to, KTO został przydzielony, o tym zdecydował już min-cost flow powyżej.
        for akt_pk in akt_assignments:
            akt_assignments[akt_pk].sort(key=lambda w: (-w['kompetencja_uzyta'], w['nazwisko']))

        return akt_assignments, uzyci_etat, uzyci_apt

    result: dict = {}
    globally_absent_shown: set[int] = set()  # nieobecni już umieszczeni w fillers jakiejś zmiany
    litera_map = KonfiguracjaZmian.pobierz().jako_slownik()

    # Pętla przez 3 zmiany (I, II, III); zmiana D obsługiwana osobno po pętli
    for zmiana in (1, 2, 3):
        litera = litera_map[zmiana]

        # Aktywności tej zmiany posortowane od największego zapotrzebowania
        shift_acts: list[tuple] = []   # (akt_pk, capacity, godziny_dict)
        for akt_pk in sorted(akt_pks_in_plan):
            g = plan_godziny.get((akt_pk, zmiana))
            if not g:
                continue
            max_wymagane = max(g.values(), default=0.0)
            if max_wymagane <= 0:
                continue
            # Pojemność = sufit z maksymalnego zapotrzebowania godzinowego
            shift_acts.append((akt_pk, math.ceil(max_wymagane), g))
        shift_acts.sort(key=lambda x: -x[1])

        akt_meta: dict[int, tuple] = {akt_pk: (cap, g) for akt_pk, cap, g in shift_acts}
        shift_akt_pks = {akt_pk for akt_pk, _, _ in shift_acts}

        # P1 — twardy filtr zgodności zmiany: tylko ci wchodzą do grafu przepływu tego bucketu.
        # Rozdział priorytetowi/pozostali służy WYŁĄCZNIE klasyfikacji fillerów niżej
        # (sekcja "Fillers") — o samym przydziale i tak decyduje wspólny koszt P2/P3
        # w _rozwiaz_bucket, priorytet działowy nie daje żadnej dodatkowej przewagi w grafie.
        eligible_priority = [
            p.pk for p in pracownicy
            if przydzial_flow.pasuje_zmiana(p, litera) and p.departament.upper() in _PRIORITY_DEPTS
            and p.pk not in nieobecni_pks
        ]
        eligible_others = [
            p.pk for p in pracownicy
            if przydzial_flow.pasuje_zmiana(p, litera) and p.departament.upper() not in _PRIORITY_DEPTS
            and p.pk not in nieobecni_pks
        ]
        eligible_etat_pks = eligible_priority + eligible_others
        eligible_apt_pks = [apt.pk for apt in apt_pracownicy if przydzial_flow.apt_pasuje_zmiana(apt, litera)]

        # Tu faktycznie zapada decyzja "kto gdzie trafia" — całą resztę funkcji
        # stanowi już tylko budowanie JSON-a wyniku i klasyfikacja nieprzydzielonych.
        akt_assignments, uzyci_etat, uzyci_apt = _rozwiaz_bucket(
            eligible_etat_pks, eligible_apt_pks, shift_acts
        )

        # Kto z uprawnionych NIE dostał miejsca — trafi do sekcji fillers niżej
        unassigned_priority = {pk for pk in eligible_priority if pk not in uzyci_etat}
        unassigned_others = {pk for pk in eligible_others if pk not in uzyci_etat}
        unassigned_apt = {pk for pk in eligible_apt_pks if pk not in uzyci_apt}

        # Zbuduj wynik zmiany jako słownik: str(akt_pk) → dane aktywności
        zmiana_result: dict = {}
        for akt_pk, _, _ in sorted(shift_acts, key=lambda x: akt_cache[x[0]].nazwa):
            workers = akt_assignments.get(akt_pk, [])
            capacity, godziny = akt_meta[akt_pk]
            akt = akt_cache[akt_pk]
            zmiana_result[str(akt_pk)] = {
                'nazwa': akt.nazwa,
                'dzial': akt.dzial,
                'wymagana': capacity,
                'pracownicy': workers,
                'godziny': {str(h): v for h, v in sorted(godziny.items())},
            }

        # Fillers — pracownicy nieprzydzieleni z powodem (capacity/no_match/no_activities)
        fillers: list[dict] = []
        for pk in (*unassigned_priority, *unassigned_others):
            obj = pk_to_p[pk]
            if shift_akt_pks and any(
                _pasuje_do_aktywnosci(obj, _norm(akt_cache[apk].nazwa), akt_cache[apk].dzial)
                or apk in komp_map.get(pk, set())
                or worker_group_score.get((pk, apk), 0.0) > 0
                for apk in shift_akt_pks
            ):
                powod = 'capacity'    # pasuje ale nie ma miejsca
            elif not shift_akt_pks:
                powod = 'no_activities'
            else:
                powod = 'no_match'    # nie pasuje do żadnej aktywności
            fillers.append({'pk': pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                            'zmiana_grupa': obj.zmiana_grupa,
                            'nieobecny': False, 'powod': powod,
                            'sektor': _sektor(obj.arkusz),
                            'wynik': None, 'zapychacz': True, 'apt': False})
        # Nieobecni tej zmiany → fillers z flagą nieobecny=True
        for p in pracownicy:
            if p.pk not in nieobecni_pks or p.pk in globally_absent_shown:
                continue
            if przydzial_flow.pasuje_zmiana(p, litera):
                fillers.append({'pk': p.pk, 'imie': p.imie, 'nazwisko': p.nazwisko,
                                'zmiana_grupa': p.zmiana_grupa,
                                'nieobecny': True, 'powod': 'nieobecny',
                                'sektor': _sektor(p.arkusz),
                                'wynik': None, 'zapychacz': True, 'apt': False})
                globally_absent_shown.add(p.pk)
        # Nieprzydzieleni APT → fillers
        for apt_pk in unassigned_apt:
            obj = apt_pk_to_p[apt_pk]
            powod_apt = ('capacity' if any(comp_apt.get((apt_pk, apk), 0.0) > 0 for apk in shift_akt_pks)
                         else 'no_match')
            fillers.append({'pk': apt_pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                            'zmiana_grupa': obj.grupa,
                            'nieobecny': False, 'powod': powod_apt,
                            'wynik': None, 'zapychacz': True, 'apt': True})
        if fillers:
            # Zlicz powody fillers dla statystyk wyświetlanych w UI
            powody_cnt = {
                'nieobecny': sum(1 for f in fillers if f.get('nieobecny')),
                'capacity':  sum(1 for f in fillers if f.get('powod') == 'capacity'),
                'no_match':  sum(1 for f in fillers if f.get('powod') == 'no_match'),
            }
            zmiana_result['__fillers__'] = {
                'nazwa': '(bez przypisanej aktywności)',
                'dzial': '',
                'wymagana': len(fillers),
                'pracownicy': sorted(fillers, key=lambda w: (w['nazwisko'], w['imie'])),
                'powody': powody_cnt,
                'godziny': {},
            }

        result[str(zmiana)] = zmiana_result

    # ─── Zmiana D (PRASA / KDR) — osobna logika dla pracowników ze zmiana_grupy zaczynającej się od 'D' ───
    litera_d = litera_map.get(4, 'D')
    d_pracownicy = [p for p in pracownicy if przydzial_flow.pasuje_zmiana(p, litera_d)]
    d_prac_pks: set[int] = {p.pk for p in d_pracownicy}

    if d_prac_pks:
        # Grupy procesowe powiązane z Prasą/KDR
        _D_GROUPS = {24, 56}
        _D_DEPT_KW = frozenset({'kdr', 'zwrot', 'prasa'})
        # Znajdź aktywności przynależne do zmiany D na podstawie grupy procesowej lub departamentu PR
        d_akt_pks: set[int] = set()
        for akt_pk in akt_pks_in_plan:
            akt = akt_cache[akt_pk]
            groups = _find_all_groups(akt.nazwa)
            dzial_n = _norm(akt.dzial)
            in_d_dept = any(kw in dzial_n for kw in _D_DEPT_KW)
            if ((any(g['nr'] in _D_GROUPS for g in groups) and in_d_dept)
                    or _dept_matches_akt('PR', akt.dzial)):
                d_akt_pks.add(akt_pk)

        # Godziny D: agregacja max ze wszystkich zmian (D obejmuje cały dzień)
        d_act_godziny: dict[int, dict[int, float]] = {}
        for akt_pk in d_akt_pks:
            agg: dict[int, float] = {}
            for z in (1, 2, 3):
                for h, v in plan_godziny.get((akt_pk, z), {}).items():
                    agg[h] = max(agg.get(h, 0.0), v)
            if agg:
                d_act_godziny[akt_pk] = agg

        d_shift_acts: list[tuple] = []
        for akt_pk in sorted(d_akt_pks):
            g = d_act_godziny.get(akt_pk)
            if not g:
                continue
            max_wym = max(g.values(), default=0.0)
            if max_wym <= 0:
                continue
            d_shift_acts.append((akt_pk, math.ceil(max_wym), g))
        d_shift_acts.sort(key=lambda x: -x[1])

        d_akt_meta: dict[int, tuple] = {apk: (cap, g) for apk, cap, g in d_shift_acts}
        d_shift_akt_pks = {apk for apk, _, _ in d_shift_acts}

        d_eligible_etat = [pk for pk in d_prac_pks if pk not in nieobecni_pks]
        d_eligible_apt = [apt.pk for apt in apt_pracownicy if (apt.grupa or '').upper().startswith(litera_d)]

        d_akt_assignments, d_uzyci_etat, d_uzyci_apt = _rozwiaz_bucket(
            d_eligible_etat, d_eligible_apt, d_shift_acts
        )

        d_unassigned = {pk for pk in d_eligible_etat if pk not in d_uzyci_etat}
        d_unassigned_apt = {pk for pk in d_eligible_apt if pk not in d_uzyci_apt}

        # Zbuduj wynik zmiany D
        d_result: dict = {}
        for apk, _, _ in sorted(d_shift_acts, key=lambda x: akt_cache[x[0]].nazwa):
            workers = d_akt_assignments.get(apk, [])
            cap, godziny_d = d_akt_meta[apk]
            akt = akt_cache[apk]
            d_result[str(apk)] = {
                'nazwa': akt.nazwa,
                'dzial': akt.dzial,
                'wymagana': cap,
                'pracownicy': workers,
                'godziny': {str(h): v for h, v in sorted(godziny_d.items())},
            }

        # Fillers D (ta sama logika co zmiana 1/2/3)
        d_fillers: list[dict] = []
        for wpk in d_unassigned:
            obj = pk_to_p[wpk]
            powod_d = ('capacity' if d_shift_akt_pks and any(
                _pasuje_do_aktywnosci(obj, _norm(akt_cache[apk].nazwa), akt_cache[apk].dzial)
                or apk in komp_map.get(wpk, set())
                or worker_group_score.get((wpk, apk), 0.0) > 0
                for apk in d_shift_akt_pks
            ) else ('no_activities' if not d_shift_akt_pks else 'no_match'))
            d_fillers.append({'pk': wpk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                              'zmiana_grupa': obj.zmiana_grupa,
                              'nieobecny': False, 'powod': powod_d,
                              'sektor': _sektor(obj.arkusz),
                              'wynik': None, 'zapychacz': True, 'apt': False})
        # Nieobecni D → fillers z flagą
        for p in d_pracownicy:
            if p.pk in nieobecni_pks and p.pk not in globally_absent_shown:
                d_fillers.append({'pk': p.pk, 'imie': p.imie, 'nazwisko': p.nazwisko,
                                  'zmiana_grupa': p.zmiana_grupa,
                                  'nieobecny': True, 'powod': 'nieobecny',
                                  'sektor': _sektor(p.arkusz),
                                  'wynik': None, 'zapychacz': True, 'apt': False})
                globally_absent_shown.add(p.pk)
        for apt_pk in d_unassigned_apt:
            obj = apt_pk_to_p[apt_pk]
            powod_apt_d = ('capacity' if any(comp_apt.get((apt_pk, apk), 0.0) > 0 for apk in d_shift_akt_pks)
                           else 'no_match')
            d_fillers.append({'pk': apt_pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                              'zmiana_grupa': obj.grupa,
                              'nieobecny': False, 'powod': powod_apt_d,
                              'wynik': None, 'zapychacz': True, 'apt': True})
        if d_fillers:
            d_powody = {
                'nieobecny': sum(1 for f in d_fillers if f.get('nieobecny')),
                'capacity':  sum(1 for f in d_fillers if f.get('powod') == 'capacity'),
                'no_match':  sum(1 for f in d_fillers if f.get('powod') == 'no_match'),
            }
            d_result['__fillers__'] = {
                'nazwa': '(bez przypisanej aktywności)',
                'dzial': '',
                'wymagana': len(d_fillers),
                'pracownicy': sorted(d_fillers, key=lambda w: (w['nazwisko'], w['imie'])),
                'powody': d_powody,
                'godziny': {},
            }

        # Wynik zmiany D zapisany pod kluczem "4"
        result['4'] = d_result

    # === POST-PROCESSING: pracownicy "bez zmiany" wypełniają pozostałą pojemność zmian 1-3 ===
    # P1 nie ma tu zastosowania (brak przypisanej zmiany) — zwolnieni z twardego filtra,
    # ale nadal kosztowani przez P2/P3 jak każdy inny pracownik etatowy. Rozwiązywane jako
    # flow na resztkowej pojemności każdej zmiany (globalnie optymalne wypełnienie luk,
    # nie zachłanne "największa luka pierwsza" jak w poprzedniej wersji algorytmu).
    bez_zmiany_prac = [
        p for p in pracownicy
        if not (p.zmiana or '').strip() and not (p.zmiana_grupa or '').strip()
    ]
    unassigned_bz_pks: set[int] = {p.pk for p in bez_zmiany_prac if p.pk not in nieobecni_pks}

    if unassigned_bz_pks:
        for zmiana_str in ['1', '2', '3']:
            if zmiana_str not in result:
                continue
            # Ile miejsc zostało wolnych PO głównym przebiegu etat+APT tej zmiany —
            # przeliczane na nowo w każdej iteracji, bo poprzednia iteracja (inna zmiana)
            # mogła nie zmienić nic tutaj, ale kolejność zmian 1→2→3 musi być zachowana
            # (pracownik "bez zmiany" zużyty w zmianie 1 nie może też trafić do zmiany 2).
            residual_spec = []
            for akt_key, akt_data in result[zmiana_str].items():
                if akt_key == '__fillers__':
                    continue
                residual = akt_data['wymagana'] - len(akt_data['pracownicy'])
                if residual > 0:
                    residual_spec.append({'pk': int(akt_key), 'capacity': residual})
            if not residual_spec:
                continue  # ta zmiana jest już w pełni obsadzona, nie ma czego szukać

            bz_spec = [{'key': pk} for pk in unassigned_bz_pks]
            bz_wynik = przydzial_flow.rozwiaz_zmiane(bz_spec, residual_spec, _koszt_etat)
            for akt_pk_bz, przydzieleni in bz_wynik.items():
                if not przydzieleni:
                    continue
                akt_key_bz = str(akt_pk_bz)
                for pk, koszt in przydzieleni:
                    result[zmiana_str][akt_key_bz]['pracownicy'].append(
                        _worker_dict(pk, pk_to_p[pk], koszt, apt=False)
                    )
                    unassigned_bz_pks.discard(pk)
                result[zmiana_str][akt_key_bz]['pracownicy'].sort(
                    key=lambda w: (-w['kompetencja_uzyta'], w['nazwisko'])
                )

    # === POST-PROCESSING 2: pozostali (jeszcze nieużyci) pracownicy APT wypełniają resztę ===
    # Każdy pracownik APT może zostać przydzielony dokładnie raz w całym dniu — śledzone
    # globalnie po wszystkich bucketach (1/2/3/4), nie tylko w obrębie tego przebiegu.
    apt_globally_used: set[int] = {
        int(w['pk'])
        for zk in ('1', '2', '3', '4')
        for akt in result.get(zk, {}).values()
        for w in akt.get('pracownicy', [])
        if w.get('apt')
    }

    for zmiana_str in ['1', '2', '3']:
        if zmiana_str not in result:
            continue
        residual_spec = []
        for akt_key, akt_data in result[zmiana_str].items():
            if akt_key == '__fillers__':
                continue
            residual = akt_data['wymagana'] - len(akt_data['pracownicy'])
            if residual > 0:
                residual_spec.append({'pk': int(akt_key), 'capacity': residual})
        if not residual_spec:
            continue

        # APT jeszcze nieużyty w ŻADNYM bucketcie (main loop 1/2/3/4 ani wcześniejszy
        # przebieg tej samej pętli dla innej zmiany_str — apt_globally_used aktualizowane niżej)
        pozostali_apt = [apt.pk for apt in apt_pracownicy if apt.pk not in apt_globally_used]
        if not pozostali_apt:
            continue
        apt_spec = [{'key': pk} for pk in pozostali_apt]
        apt_wynik = przydzial_flow.rozwiaz_zmiane(apt_spec, residual_spec, _koszt_apt)
        for akt_pk_a, przydzieleni in apt_wynik.items():
            if not przydzieleni:
                continue
            akt_key_a = str(akt_pk_a)
            for pk, koszt in przydzieleni:
                result[zmiana_str][akt_key_a]['pracownicy'].append(
                    _worker_dict(pk, apt_pk_to_p[pk], koszt, apt=True)
                )
                apt_globally_used.add(pk)
            result[zmiana_str][akt_key_a]['pracownicy'].sort(
                key=lambda w: (-w['kompetencja_uzyta'], w['nazwisko'])
            )

    # Pracownicy "bez zmiany" bez żadnego dopasowania + nieobecni bez zmiany → sekcja "0"
    bez_zmiany_remaining = [
        p for p in bez_zmiany_prac
        if p.pk in unassigned_bz_pks or p.pk in nieobecni_pks
    ]
    if bez_zmiany_remaining:
        bz_fillers = sorted([
            {'pk': p.pk, 'imie': p.imie, 'nazwisko': p.nazwisko,
             'zmiana_grupa': '', 'nieobecny': p.pk in nieobecni_pks,
             'powod': 'nieobecny' if p.pk in nieobecni_pks else 'no_match',
             'sektor': _sektor(p.arkusz),
             'wynik': None, 'zapychacz': True, 'apt': False}
            for p in bez_zmiany_remaining
        ], key=lambda w: (w['nazwisko'], w['imie']))
        result['0'] = {
            '__fillers__': {
                'nazwa': '(bez przypisanej aktywności)',
                'dzial': '',
                'wymagana': len(bz_fillers),
                'pracownicy': bz_fillers,
                'powody': {
                    'nieobecny': sum(1 for f in bz_fillers if f['nieobecny']),
                    'capacity': 0,
                    'no_match': sum(1 for f in bz_fillers if not f['nieobecny']),
                },
                'godziny': {},
            }
        }

    # Ostrzeżenia z crosswalku (P2, strefa niepewności 0.70-0.85) — jeśli żadne nie
    # wystąpiło, nie zaśmiecamy JSON-a pustą listą pod niepotrzebnym kluczem
    if ostrzezenia_dzialow:
        result['__ostrzezenia_dzialow__'] = ostrzezenia_dzialow

    return result


# Wywołuje algorytm przydziału i zapisuje/aktualizuje PrzydzialDzienny dla planu
@login_required
def przydziel_plan(request, pk):
    if request.method != 'POST':
        return redirect('pracownicy:plany_lista')
    plan = get_object_or_404(PlanDzienny, pk=pk)
    # Brak pracowników = niemożliwy przydział
    if not Pracownik.objects.exists():
        messages.error(request, 'Brak pracowników w bazie — najpierw zaimportuj pracowników.')
        return redirect('pracownicy:plany_lista')
    try:
        dane = _wykonaj_przydzial(plan)
        # update_or_create: jeśli plan miał już przydział — nadpisuje go nowym
        PrzydzialDzienny.objects.update_or_create(plan=plan, defaults={'dane': dane})
        messages.success(request, f'Przydzielono pracowników do planu „{plan.nazwa_pliku}".')
    except Exception as exc:
        messages.error(request, f'Błąd przydziału: {exc}')
        return redirect('pracownicy:plany_lista')
    return redirect('pracownicy:wyniki_przydzialu', pk=pk)


# Etykiety zmian wyświetlane w nagłówkach sekcji na stronie wyników
ZMIANA_NAZWA = {
    0: 'Bez przypisanej zmiany',
    1: 'Zmiana I (6–13)',
    2: 'Zmiana II (14–21)',
    3: 'Zmiana III (22–5)',
    4: 'Zmiana D (PRASA/KDR)',
}


# Wyświetla wyniki przydziału: tabele z pracownikami per zmiana i aktywność + dane do modali
@login_required
def wyniki_przydzialu(request, pk):
    plan = get_object_or_404(PlanDzienny, pk=pk)
    try:
        przydzial = plan.przydzial
    except PrzydzialDzienny.DoesNotExist:
        messages.info(request, 'Ten plan nie ma jeszcze przydziału. Kliknij „Przypisz pracowników".')
        return redirect('pracownicy:plany_lista')

    zmiany_dane: dict = {}
    for zmiana_str, akt_dict in przydzial.dane.items():
        zmiana_int = int(zmiana_str)
        dzialy_org: dict = {}
        total_pracownicy = total_fillers = 0

        for akt_key, akt_data in akt_dict.items():
            n = len(akt_data['pracownicy'])
            akt_data['przydzielono'] = n
            # kompletny = True jeśli przydzielono co najmniej tylu ile wymagano
            akt_data['kompletny'] = (n >= akt_data.get('wymagana', n))

            if akt_key == '__fillers__':
                akt_data['dzial'] = ''
                total_fillers += n
                prac = akt_data['pracownicy']
                # Uzupełnij sektor z DB dla starych JSON które go nie mają (backward compat)
                etat_prac = [p for p in prac if not p.get('apt')]
                missing_sektor_pks = [p['pk'] for p in etat_prac if 'sektor' not in p]
                if missing_sektor_pks:
                    arkusz_map = dict(
                        Pracownik.objects.filter(pk__in=missing_sektor_pks)
                        .values_list('pk', 'arkusz')
                    )
                    for p in etat_prac:
                        if 'sektor' not in p:
                            p['sektor'] = _sektor(arkusz_map.get(p['pk'], ''))
                akt_data['pracownicy_etat'] = etat_prac
                akt_data['pracownicy_apt_list'] = [p for p in prac if p.get('apt')]
                dzialy_org.setdefault('(bez przypisanej aktywności)', []).append(akt_data)
            else:
                dzial = akt_data['dzial'] or '(bez działu)'
                dzialy_org.setdefault(dzial, []).append(akt_data)
                total_pracownicy += n

        # Sortuj aktywności alfabetycznie w każdym dziale
        for lst in dzialy_org.values():
            lst.sort(key=lambda x: x['nazwa'])

        # Sekcja fillers zawsze na końcu (po wszystkich działach)
        dzialy_sorted = {k: v for k, v in sorted(dzialy_org.items())
                         if k != '(bez przypisanej aktywności)'}
        if '(bez przypisanej aktywności)' in dzialy_org:
            dzialy_sorted['(bez przypisanej aktywności)'] = dzialy_org['(bez przypisanej aktywności)']

        zmiany_dane[zmiana_int] = {
            'nazwa': ZMIANA_NAZWA.get(zmiana_int, f'Zmiana {zmiana_int}'),
            'dzialy': dzialy_sorted,
            'total_pracownicy': total_pracownicy,
            'total_fillers': total_fillers,
        }

    # Kolejność godzin dla każdej zmiany (zmiana III przekracza północ)
    _zmiana_godziny = {
        1: [6, 7, 8, 9, 10, 11, 12, 13],
        2: [14, 15, 16, 17, 18, 19, 20, 21],
        3: [22, 23, 0, 1, 2, 3, 4, 5],
    }
    # Godziny D: wyznacz dynamicznie z rzeczywistych danych (D może mieć różne godziny)
    if 4 in zmiany_dane:
        _d_hours: set[int] = set()
        for _akts_d in zmiany_dane[4]['dzialy'].values():
            for _akt_d in _akts_d:
                for _h_str, _v in (_akt_d.get('godziny') or {}).items():
                    if _v > 0:
                        _d_hours.add(int(_h_str))
        # Sortuj godziny chronologicznie (godziny < 6 to "jutro" — przekształć na +24 dla sortowania)
        _zmiana_godziny[4] = sorted(_d_hours, key=lambda h: h if h >= 6 else h + 24)

    # Dodaj godziny_ordered (lista [[godzina, wymagane_osoby], ...]) do każdej aktywności
    for zmiana_int, zd in zmiany_dane.items():
        hour_order = _zmiana_godziny.get(zmiana_int, [])
        for aktywnosci in zd['dzialy'].values():
            for akt_data in aktywnosci:
                g = akt_data.get('godziny') or {}
                akt_data['godziny_ordered'] = [
                    [h, g.get(str(h), 0.0)] for h in hour_order
                ]

    # Mapowanie nazwa_działu → kod strefy (do kolorowania sekcji w UI)
    all_dzialy: set[str] = set()
    for zd in zmiany_dane.values():
        all_dzialy.update(zd['dzialy'].keys())
    dzial_dept = {d: _dept_for_dzial(d) for d in all_dzialy}

    litera_map = KonfiguracjaZmian.pobierz().jako_slownik()

    # --- Przygotowanie danych JSON dla modali ---
    # (bezpiecznie osadzone w szablonie przez {{ zmienna|json_script:"id" }})
    _db_akt_names = set(Aktywnosc.objects.values_list('nazwa', flat=True))

    # Zbierz PKi wszystkich pracowników etatowych z planu
    all_plan_worker_pks: set[int] = set()
    for _zd in zmiany_dane.values():
        for _akts in _zd['dzialy'].values():
            for _akt in _akts:
                for _p in _akt.get('pracownicy', []):
                    if not _p.get('apt'):
                        all_plan_worker_pks.add(_p['pk'])

    # Top 4 kompetencje per pracownik (posortowane wg wyniku desc) — wyświetlane w modalu pracownika
    worker_top_komp: dict[int, list[dict]] = {}
    if all_plan_worker_pks:
        _komp_rows = (KompetencjaPracownika.objects
                      .filter(pracownik_id__in=all_plan_worker_pks, wynik__gt=0)
                      .select_related('aktywnosc')
                      .order_by('pracownik_id', '-wynik'))
        # Grupuj kompetencje per pracownik (posortowane już po pracowniku i wyniku)
        _cur_pk: int | None = None
        _cur_lst: list = []
        for _k in _komp_rows:
            if _k.pracownik_id != _cur_pk:
                if _cur_pk is not None:
                    worker_top_komp[_cur_pk] = _cur_lst
                _cur_pk = _k.pracownik_id
                _cur_lst = []
            if len(_cur_lst) < 4:
                _cur_lst.append({'nazwa': _k.aktywnosc.nazwa, 'wynik': float(_k.wynik)})
        if _cur_pk is not None:
            worker_top_komp[_cur_pk] = _cur_lst

    # worker_data: pk → dane wyświetlane w modalu kliknięcia na badge pracownika
    worker_data: dict[int, dict] = {}
    for _zd in zmiany_dane.values():
        for _akts in _zd['dzialy'].values():
            for _akt in _akts:
                for _p in _akt.get('pracownicy', []):
                    _wpk = _p['pk']
                    if _wpk not in worker_data:
                        worker_data[_wpk] = {
                            'imie': _p['imie'],
                            'nazwisko': _p['nazwisko'],
                            'zmiana_grupa': _p.get('zmiana_grupa') or '',
                            'wynik': _p.get('wynik'),
                            'top_komp': worker_top_komp.get(_wpk, []),
                        }

    # Konwertuje listę grup procesowych na format używany w modalu aktywności
    def _groups_to_info(groups: list[dict]) -> list[dict]:
        return [
            {
                'nr': _g['nr'],
                'nazwa': _g['nazwa'],
                # w_db=True → czynność zielona w modalu (istnieje jako aktywność w DB)
                'czynnosci': [
                    {'nazwa': _c, 'w_db': _c in _db_akt_names}
                    for _c in _g['czynnosci']
                ],
            }
            for _g in groups
        ]

    # modal_data: nazwa_aktywności → {grupy procesowe + pracownicy z wynikami}
    # Używane przez kliknięcie na nazwę aktywności (przycisk .akt-modal-trigger)
    modal_data: dict[str, dict] = {}
    _seen: set[str] = set()
    for _zd in zmiany_dane.values():
        for _akts in _zd['dzialy'].values():
            for _akt in _akts:
                _nazwa = _akt.get('nazwa', '')
                if not _nazwa or _nazwa == '(bez przypisanej aktywności)' or _nazwa in _seen:
                    continue
                _seen.add(_nazwa)
                # Tylko pracownicy którzy mają wynik (score z macierzy) — do wyświetlenia w modalu
                _workers_scored = [
                    {
                        'pk': _p['pk'],
                        'imie': _p['imie'],
                        'nazwisko': _p['nazwisko'],
                        'zmiana_grupa': _p.get('zmiana_grupa') or '',
                        'wynik': _p['wynik'],
                        'top_komp': worker_top_komp.get(_p['pk'], []),
                    }
                    for _p in _akt.get('pracownicy', []) if _p.get('wynik')
                ]
                modal_data[_nazwa] = {
                    'groups': _groups_to_info(_find_all_groups(_nazwa)),
                    'workers': _workers_scored,
                }

    # Oblicz rankingi pracowników w grupach procesowych (wyświetlane w modalu pracownika)
    _db_akt_pk_map = {a.nazwa: a.pk for a in Aktywnosc.objects.only('pk', 'nazwa')}
    _gpk_to_g: dict[int, dict] = {}
    for _g in _GP:
        for _c in _g['czynnosci']:
            _pk2 = _db_akt_pk_map.get(_c)
            if _pk2:
                _gpk_to_g[_pk2] = _g

    # Akumuluj sumy wyników per (pracownik, numer_grupy) do obliczenia średniej
    _wpk_grp_sums: dict[tuple, float] = {}
    _wpk_grp_cnts: dict[tuple, int] = {}
    for _row in (KompetencjaPracownika.objects
                 .filter(aktywnosc_id__in=_gpk_to_g.keys(), wynik__gt=0)
                 .values('pracownik_id', 'aktywnosc_id', 'wynik')):
        _g2 = _gpk_to_g.get(_row['aktywnosc_id'])
        if not _g2:
            continue
        _key2 = (_row['pracownik_id'], _g2['nr'])
        _wpk_grp_sums[_key2] = _wpk_grp_sums.get(_key2, 0.0) + float(_row['wynik'])
        _wpk_grp_cnts[_key2] = _wpk_grp_cnts.get(_key2, 0) + 1

    # Ranking per grupa: numer_grupy → [(worker_pk, avg)] posortowane malejąco
    _grp_rankings: dict[int, list] = {}
    for (_wpk2, _gnr), _s in _wpk_grp_sums.items():
        _avg2 = round(_s / _wpk_grp_cnts[(_wpk2, _gnr)], 1)
        _grp_rankings.setdefault(_gnr, []).append((_wpk2, _avg2))
    for _gnr in _grp_rankings:
        _grp_rankings[_gnr].sort(key=lambda x: -x[1])

    _grp_info_map = {_g['nr']: _g for _g in _GP}
    # Dla każdego pracownika z planu: lista grup z jego pozycją w rankingu
    _worker_grp_ranks: dict[int, list] = {}
    for _gnr, _ranking in _grp_rankings.items():
        for _rank, (_wpk2, _avg2) in enumerate(_ranking, 1):
            if _wpk2 not in all_plan_worker_pks:
                continue
            _worker_grp_ranks.setdefault(_wpk2, []).append({
                'nr': _gnr,
                'nazwa': _grp_info_map[_gnr]['nazwa'],
                'rank': _rank,
                'score': _avg2,
            })
    # Sortuj rankingi pracownika malejąco po score (najlepsza grupa na górze)
    for _wpk2 in _worker_grp_ranks:
        _worker_grp_ranks[_wpk2].sort(key=lambda x: -x['score'])

    # Dołącz rankingi grup do danych pracownika
    for _wpk2, _wdata in worker_data.items():
        _wdata['group_rankings'] = _worker_grp_ranks.get(_wpk2, [])

    # dzial_modal_data: nazwa_działu → grupy procesowe wszystkich aktywności tego działu
    # Używane przez kliknięcie na nagłówek działu (.dzial-modal-trigger)
    dzial_modal_data: dict[str, dict] = {}
    for _zd in zmiany_dane.values():
        for _dzial_nazwa, _akts_d in _zd['dzialy'].items():
            if _dzial_nazwa in dzial_modal_data or _dzial_nazwa == '(bez przypisanej aktywności)':
                continue
            _groups_for_dzial: dict[int, dict] = {}
            for _akt_d in _akts_d:
                _an = _akt_d.get('nazwa', '')
                for _grp_d in _find_all_groups(_an):
                    if _grp_d['nr'] not in _groups_for_dzial:
                        _groups_for_dzial[_grp_d['nr']] = {
                            'nr': _grp_d['nr'],
                            'nazwa': _grp_d['nazwa'],
                            'czynnosci': [
                                {'nazwa': _c, 'w_db': _c in _db_akt_names}
                                for _c in _grp_d['czynnosci']
                            ],
                        }
            dzial_modal_data[_dzial_nazwa] = {
                'groups': sorted(_groups_for_dzial.values(), key=lambda x: x['nr']),
            }

    return render(request, 'pracownicy/wyniki_przydzialu.html', {
        'plan': plan,
        'przydzial': przydzial,
        'zmiany_dane': dict(sorted(zmiany_dane.items(), key=lambda x: (x[0] == 0, x[0]))),
        'dzial_dept': dzial_dept,
        'litera_map': litera_map,
        # Dane JSON dla modali — bezpiecznie osadzone przez json_script w szablonie
        'modal_data': modal_data,
        'worker_data': {str(pk): v for pk, v in worker_data.items()},
        'dzial_data': dzial_modal_data,
    })


# ── Lista pracowników APT ──────────────────────────────────────────────────────

# Lista pracowników agencyjnych z liczbą ocen i paginacją (50 na stronę)
@login_required
def lista_pracownikow_apt(request):
    qs = PracownikAPT.objects.annotate(
        liczba_ocen=Count('oceny')
    ).order_by('nazwisko', 'imie')
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    pr, pr_start, pr_end = _page_range(page_obj, paginator)
    return render(request, 'pracownicy/lista_pracownikow_apt.html', {
        'pracownicy_apt': page_obj,
        'page_range': pr,
        'pr_start': pr_start,
        'pr_end': pr_end,
    })


# ── Import: plan zmianowy ──────────────────────────────────────────────────────

# Widok importu planu zmianowego — obsługuje trzy akcje: upload, confirm, save_config
@login_required
def import_plan_zmianowy(request):
    plany_count = PlanDzienny.objects.count()

    # GET — wyświetl formularz z aktualną konfiguracją zmian
    if request.method == 'GET':
        return render(request, 'pracownicy/import_plan_zmianowy.html', {
            'plany_count': plany_count,
            'konfig_zmian': KonfiguracjaZmian.pobierz(),
        })

    action = request.POST.get('action', 'upload')

    # Akcja: zapisz konfigurację liter zmian (I=A/B/C, II=A/B/C, III=A/B/C)
    if action == 'save_config':
        cfg = KonfiguracjaZmian.pobierz()
        z1 = request.POST.get('zmiana_1', 'A')
        z2 = request.POST.get('zmiana_2', 'B')
        z3 = request.POST.get('zmiana_3', 'C')
        valid = {'A', 'B', 'C'}
        # Każda litera musi być użyta dokładnie raz (bez duplikatów)
        if z1 in valid and z2 in valid and z3 in valid and len({z1, z2, z3}) == 3:
            cfg.zmiana_1, cfg.zmiana_2, cfg.zmiana_3 = z1, z2, z3
            cfg.save()
            messages.success(request, f'Konfiguracja zmian zapisana: I={z1}, II={z2}, III={z3}.')
        else:
            messages.error(request, 'Nieprawidłowa konfiguracja — każda litera (A/B/C) musi być użyta dokładnie raz.')
        return redirect('import_danych:import_plan_zmianowy')

    # Akcja: potwierdź import (użytkownik kliknął "Importuj" po podglądzie)
    if action == 'confirm':
        tmp_uuid = request.POST.get('tmp_uuid', '')
        tmp_path = _tmp_dir() / f'{tmp_uuid}.json'
        # Plik tymczasowy może wygasnąć jeśli użytkownik odczekał zbyt długo
        if not tmp_path.exists():
            messages.error(request, 'Sesja importu wygasła — prześlij plik ponownie.')
            return redirect('import_danych:import_plan_zmianowy')
        try:
            data = json.loads(tmp_path.read_text(encoding='utf-8'))
            _zapisz_plan_dzienny(data, request.user)
        except Exception as exc:
            messages.error(request, f'Błąd zapisu do bazy danych: {exc}')
            return redirect('import_danych:import_plan_zmianowy')
        finally:
            # Zawsze usuń plik tymczasowy, nawet przy błędzie
            tmp_path.unlink(missing_ok=True)

        s = data['stats']
        messages.success(
            request,
            f'Zaimportowano plan „{s["nazwa_pliku"]}": '
            f'{s["total_aktywnosci"]} aktywności, '
            f'{s["total_rekordow"]} rekordów godzinowych.',
        )
        return redirect('pracownicy:plany_lista')

    # Akcja: upload — parsuj plik i pokaż podgląd do potwierdzenia
    data_planu_raw = request.POST.get('data_planu', '').strip()
    plik = request.FILES.get('plik')
    if not plik:
        messages.error(request, 'Nie wybrano pliku.')
        return render(request, 'pracownicy/import_plan_zmianowy.html', {
            'plany_count': plany_count,
        })

    from django.core.exceptions import ValidationError as _VE
    try:
        waliduj_plik_importu(plik)
    except _VE as exc:
        messages.error(request, exc.message)
        return render(request, 'pracownicy/import_plan_zmianowy.html', {
            'plany_count': plany_count,
        })

    try:
        wiersze, ostrzezenia = parsuj_plan_dzienny(plik)
    except Exception as exc:
        messages.error(request, f'Błąd parsowania pliku: {exc}')
        return render(request, 'pracownicy/import_plan_zmianowy.html', {
            'plany_count': plany_count,
        })

    if not wiersze:
        messages.error(request, 'Nie znaleziono danych aktywności w pliku. Sprawdź czy arkusz nosi nazwę „PLAN NEW".')
        return render(request, 'pracownicy/import_plan_zmianowy.html', {
            'plany_count': plany_count,
        })

    # Zlicz aktywności per dział do statystyk podglądu
    dzialy: dict[str, int] = {}
    for w in wiersze:
        dzialy[w.dzial] = dzialy.get(w.dzial, 0) + 1

    stats = {
        'nazwa_pliku': plik.name,
        'total_aktywnosci': len(wiersze),
        'total_rekordow': len(wiersze) * 24,  # 24 rekordy godzinowe per aktywność
        'dzialy': dzialy,
    }

    # Serializuj dane do JSON — przechowaj tymczasowo w pliku (pomiędzy upload a confirm)
    data = {
        'wiersze': [
            {
                'dzial': w.dzial,
                'aktywnosc': w.aktywnosc,
                'wolumen_I': w.wolumen_I,
                'wolumen_II': w.wolumen_II,
                'wolumen_III': w.wolumen_III,
                'godziny': {
                    str(zm): {str(h): v for h, v in godziny.items()}
                    for zm, godziny in w.godziny.items()
                },
            }
            for w in wiersze
        ],
        'ostrzezenia': ostrzezenia,
        'stats': stats,
        'data_planu': data_planu_raw,
    }

    # UUID jako nazwa pliku tymczasowego — zapobiega kolizjom przy jednoczesnych importach
    tmp_id = str(uuid.uuid4())
    (_tmp_dir() / f'{tmp_id}.json').write_text(
        json.dumps(data, ensure_ascii=False), encoding='utf-8'
    )

    # Pokaż podgląd pierwszych 40 wierszy do zatwierdzenia przez użytkownika
    return render(request, 'pracownicy/import_plan_zmianowy.html', {
        'podglad': wiersze[:40],
        'stats': stats,
        'ostrzezenia': ostrzezenia,
        'tmp_uuid': tmp_id,
        'nazwa_pliku': plik.name,
        'data_planu': data_planu_raw,
        'plany_count': plany_count,
    })


# Zapisuje plan dzienny do DB z rekordami ZapotrzebowanieGodzinowe
def _zapisz_plan_dzienny(data: dict, user) -> None:
    from datetime import date as date_type
    raw = data.get('data_planu', '')
    try:
        dp = date_type.fromisoformat(raw) if raw else None
    except ValueError:
        dp = None
    # Tworzy nowy rekord PlanDzienny (nagłówek)
    plan = PlanDzienny.objects.create(
        nazwa_pliku=data['stats']['nazwa_pliku'],
        data_planu=dp,
        importowany_przez=user,
    )
    # Cache aktywności — unika wielokrotnych get_or_create dla tej samej pary (nazwa, dział)
    aktywnosci_cache: dict[tuple, int] = {}
    rekordy = []

    for wpis in data['wiersze']:
        key = (wpis['aktywnosc'], wpis['dzial'])
        if key not in aktywnosci_cache:
            # get_or_create — nie duplikuje aktywności jeśli już istnieje z poprzedniego importu
            akt, _ = Aktywnosc.objects.get_or_create(nazwa=wpis['aktywnosc'], dzial=wpis['dzial'])
            aktywnosci_cache[key] = akt.pk

        akt_pk = aktywnosci_cache[key]
        wolumeny = {1: wpis['wolumen_I'], 2: wpis['wolumen_II'], 3: wpis['wolumen_III']}

        # Utwórz 24 rekordy godzinowe per aktywność (3 zmiany × 8 godzin)
        for zmiana_str, godziny in wpis['godziny'].items():
            zmiana = int(zmiana_str)
            for godzina_str, liczba in godziny.items():
                rekordy.append(ZapotrzebowanieGodzinowe(
                    plan=plan,
                    aktywnosc_id=akt_pk,
                    zmiana=zmiana,
                    godzina=int(godzina_str),
                    liczba_osob=float(liczba),
                    wolumen=wolumeny.get(zmiana),
                ))

    # bulk_create dla wydajności — jeden INSERT zamiast setek osobnych
    ZapotrzebowanieGodzinowe.objects.bulk_create(rekordy, ignore_conflicts=True)


# ── Import: pracownicy ─────────────────────────────────────────────────────────

# Widok importu pracowników — obsługuje dwa pliki: kompetencje i struktura (oba opcjonalne)
@login_required
def import_pracownicy(request):
    pracownicy_count = Pracownik.objects.count()

    if request.method == 'GET':
        return render(request, 'pracownicy/import_pracownicy.html', {
            'pracownicy_count': pracownicy_count,
        })

    action = request.POST.get('action', 'upload')

    # Akcja: potwierdź import — odczytaj dane z pliku tymczasowego i zapisz do DB
    if action == 'confirm':
        tmp_uuid = request.POST.get('tmp_uuid', '')
        tmp_path = _tmp_dir() / f'{tmp_uuid}.json'
        if not tmp_path.exists():
            messages.error(request, 'Sesja importu wygasła — prześlij pliki ponownie.')
            return redirect('import_danych:import_pracownicy')
        try:
            data = json.loads(tmp_path.read_text(encoding='utf-8'))
            _zapisz_pracownikow(data)
            s = data['stats']
            messages.success(
                request,
                f'Zaimportowano {s["total_pracownikow"]} pracowników, '
                f'{s["total_kompetencji"]} kompetencji, '
                f'{s["total_absencji"]} absencji.',
            )
        except Exception as exc:
            messages.error(request, f'Błąd zapisu do bazy danych: {exc}')
        finally:
            tmp_path.unlink(missing_ok=True)
        return redirect('pracownicy:lista')

    # Akcja: upload — parsuj pliki i pokaż podgląd
    plik_kompetencje = request.FILES.get('plik_kompetencje')
    plik_struktura = request.FILES.get('plik_struktura')

    if not plik_kompetencje and not plik_struktura:
        messages.error(request, 'Wybierz co najmniej jeden plik.')
        return render(request, 'pracownicy/import_pracownicy.html', {
            'pracownicy_count': pracownicy_count,
        })

    # Słowniki wynikowe — scalane z obu plików (ten sam pracownik w obu)
    pracownicy_dict: dict[tuple, dict] = {}
    kompetencje_dict: dict[tuple, list] = {}
    absencje_list: list[dict] = []
    ostrzezenia: list[str] = []

    from django.core.exceptions import ValidationError as _VE
    if plik_kompetencje:
        try:
            waliduj_plik_importu(plik_kompetencje)
        except _VE as exc:
            messages.error(request, exc.message)
            return render(request, 'pracownicy/import_pracownicy.html', {
                'pracownicy_count': pracownicy_count,
            })
        try:
            p_list, k_dict, ostr = parsuj_kompetencje(plik_kompetencje)
            for p in p_list:
                key = (p['nazwisko'], p['imie'])
                # Pola strukturalne (dzial, zmiana) NIE są brane z pliku kompetencji
                # bo tam bywają niekompletne — zostaną nadpisane przez plik struktury
                _tylko_struktura = {'dzial', 'zmiana', 'zmiana_grupa'}
                p_komp = {k: v for k, v in p.items() if k not in _tylko_struktura}
                pracownicy_dict[key] = {**pracownicy_dict.get(key, {}), **p_komp}
            for key, komp in k_dict.items():
                kompetencje_dict.setdefault(key, []).extend(komp)
            ostrzezenia.extend(ostr)
        except Exception as exc:
            messages.error(request, f'Błąd parsowania pliku kompetencji: {exc}')
            return render(request, 'pracownicy/import_pracownicy.html', {
                'pracownicy_count': pracownicy_count,
            })

    if plik_struktura:
        try:
            waliduj_plik_importu(plik_struktura)
        except _VE as exc:
            messages.error(request, exc.message)
            return render(request, 'pracownicy/import_pracownicy.html', {
                'pracownicy_count': pracownicy_count,
            })
        try:
            p_list, a_list, ostr = parsuj_strukture(plik_struktura)
            for p in p_list:
                key = (p['nazwisko'], p['imie'])
                # Dane struktury nadpisują kompetencje dla tych samych pracowników (merge)
                pracownicy_dict[key] = {**pracownicy_dict.get(key, {}), **p}
            absencje_list.extend(a_list)
            ostrzezenia.extend(ostr)
        except Exception as exc:
            messages.error(request, f'Błąd parsowania pliku struktury: {exc}')
            return render(request, 'pracownicy/import_pracownicy.html', {
                'pracownicy_count': pracownicy_count,
            })

    if not pracownicy_dict:
        messages.error(request, 'Nie znaleziono pracowników w przesłanych plikach.')
        return render(request, 'pracownicy/import_pracownicy.html', {
            'pracownicy_count': pracownicy_count,
        })

    # Scal pracowników z ich kompetencjami w jeden słownik
    pracownicy_list = [
        {**pdata, 'kompetencje': kompetencje_dict.get(key, [])}
        for key, pdata in pracownicy_dict.items()
    ]

    stats = {
        'total_pracownikow': len(pracownicy_list),
        'total_kompetencji': sum(len(p['kompetencje']) for p in pracownicy_list),
        'total_absencji': len(absencje_list),
    }

    # Grupowanie per arkusz do podglądu w modalu (zakładki IB/OB/FF/ZW/PR)
    _SHEET_ORDER = ['Struktura IN', 'Struktura IB', 'Struktura OB', 'Struktura FF', 'Struktura ZW', 'Struktura PR']
    _SHEET_LABEL = {
        'Struktura IN': 'IN — Inbound',
        'Struktura IB': 'IB — Inbound',
        'Struktura OB': 'OB — Outbound',
        'Struktura FF': 'FF — Fulfilment',
        'Struktura ZW': 'ZW — Zwroty',
        'Struktura PR': 'PR — Prasa',
    }
    arkusze: dict[str, list] = {}
    for p in pracownicy_list:
        # Pracownicy tylko z pliku kompetencji (bez struktury) trafiają do osobnej zakładki
        sheet = p.get('_sheet') or 'Tylko KOMPETENCJE'
        arkusze.setdefault(sheet, []).append(p)

    podglad_arkusze = []
    seen = set()
    for sh in _SHEET_ORDER:
        if sh in arkusze:
            podglad_arkusze.append({
                'key': sh.replace(' ', '_'),
                'label': _SHEET_LABEL.get(sh, sh),
                'count': len(arkusze[sh]),
                'pracownicy': arkusze[sh][:40],  # max 40 pracowników w podglądzie
            })
            seen.add(sh)
    for sh, workers in arkusze.items():
        if sh not in seen:
            podglad_arkusze.append({
                'key': sh.replace(' ', '_'),
                'label': sh,
                'count': len(workers),
                'pracownicy': workers[:40],
            })

    data = {
        'pracownicy': pracownicy_list,
        'absencje': absencje_list,
        'ostrzezenia': ostrzezenia,
        'stats': stats,
    }

    tmp_id = str(uuid.uuid4())
    # default=str — obsługa dat (obiekt date nie jest serializowalny jako JSON)
    (_tmp_dir() / f'{tmp_id}.json').write_text(
        json.dumps(data, ensure_ascii=False, default=str), encoding='utf-8'
    )

    return render(request, 'pracownicy/import_pracownicy.html', {
        'podglad_arkusze': podglad_arkusze,
        'stats': stats,
        'ostrzezenia': ostrzezenia,
        'tmp_uuid': tmp_id,
        'plik_kompetencje_nazwa': plik_kompetencje.name if plik_kompetencje else None,
        'plik_struktura_nazwa': plik_struktura.name if plik_struktura else None,
        'pracownicy_count': pracownicy_count,
    })


# Zapisuje pracowników do DB — DESTRUKTYWNE: usuwa wszystkich i tworzy od nowa
def _zapisz_pracownikow(data: dict) -> None:
    # Usuń wszystkich istniejących pracowników (cascade usuwa kompetencje i absencje)
    Pracownik.objects.all().delete()

    nowi = []
    for p in data['pracownicy']:
        dt = p.get('data_zatrudnienia')
        if isinstance(dt, str) and dt:
            try:
                dt = date.fromisoformat(dt[:10])
            except ValueError:
                dt = None
        elif not isinstance(dt, date):
            dt = None

        zmiana     = p.get('zmiana', '').strip().upper()
        zmiana_gr  = p.get('zmiana_grupa', '').strip()
        # Normalizacja: jeśli zmiana_grupa to sama cyfra (np. "2") a zmiana to litera (np. "C")
        # → scalamy do formatu "C-2" używanego przez algorytm przydziału
        if zmiana and zmiana_gr and zmiana_gr.isdigit():
            zmiana_gr = f'{zmiana}-{zmiana_gr}'

        nowi.append(Pracownik(
            nr_ewidencyjny=p.get('nr_ewidencyjny') or None,
            imie=p.get('imie', ''),
            nazwisko=p.get('nazwisko', ''),
            departament=p.get('departament', ''),
            stanowisko=p.get('stanowisko', ''),
            strefa=p.get('strefa', ''),
            dzial=p.get('dzial', ''),
            zmiana=zmiana,
            zmiana_grupa=zmiana_gr,
            przelozony=p.get('przelozony', ''),
            komentarz=p.get('komentarz', ''),
            data_zatrudnienia=dt,
            arkusz=p.get('_sheet', ''),
        ))

    # bulk_create zwraca listę z przypisanymi PKami — potrzebne do przypisania kompetencji
    created = Pracownik.objects.bulk_create(nowi)
    # Mapa (imie, nazwisko) → pk — do wiązania kompetencji i absencji z pracownikiem
    pk_by_name: dict[tuple, int] = {(p.imie, p.nazwisko): p.pk for p in created}

    # Zapisz kompetencje dla każdego pracownika
    aktywnosci_cache: dict[tuple, int] = {}
    komp_objs = []
    for prac_data, prac_obj in zip(data['pracownicy'], created):
        for k in prac_data.get('kompetencje', []):
            key = (k['aktywnosc_nazwa'], k['aktywnosc_dzial'])
            if key not in aktywnosci_cache:
                akt, _ = Aktywnosc.objects.get_or_create(
                    nazwa=k['aktywnosc_nazwa'], dzial=k['aktywnosc_dzial']
                )
                aktywnosci_cache[key] = akt.pk
            komp_objs.append(KompetencjaPracownika(
                pracownik_id=prac_obj.pk,
                aktywnosc_id=aktywnosci_cache[key],
                wynik=k['wynik'],
            ))
    KompetencjaPracownika.objects.bulk_create(komp_objs, ignore_conflicts=True)

    # Zapisz absencje — klucz format "Nazwisko|Imie" (z parsera struktury)
    abs_objs = []
    for a in data['absencje']:
        klucz = a.get('pracownik_klucz', '')
        if '|' not in klucz:
            continue
        nazwisko, imie = klucz.split('|', 1)
        pk = pk_by_name.get((imie, nazwisko))
        if pk is None:
            continue  # pracownik z absencją nie istnieje (tylko w strukturze, nie w kompetencjach)
        try:
            d = date.fromisoformat(a['data'][:10])
        except (ValueError, KeyError):
            continue
        abs_objs.append(AbsencjaPracownika(pracownik_id=pk, data=d, typ=a['typ']))
    AbsencjaPracownika.objects.bulk_create(abs_objs, ignore_conflicts=True)


# ── Import: pracownicy APT ─────────────────────────────────────────────────────

# Widok importu APT — obsługuje trzy akcje: upload, confirm, save_mapping (konfiguracja kolumn)
@login_required
def import_pracownicy_apt(request):
    # Aktualne mapowanie kolumn (1–14) → nazwy działów
    kolumny = {k.numer_kolumny: k.nazwa_dzialu for k in KolumnaAPT.objects.all()}
    apt_count = PracownikAPT.objects.count()
    base_ctx = {'kolumny': kolumny, 'numery_kolumn': range(1, 15), 'apt_count': apt_count}

    if request.method == 'GET':
        return render(request, 'pracownicy/import_pracownicy_apt.html', base_ctx)

    action = request.POST.get('action', 'upload')

    # Akcja: zapisz mapowanie kolumn (admin przypisuje kolumny do działów)
    if action == 'save_mapping':
        KolumnaAPT.objects.all().delete()
        nowe = []
        for i in range(1, 15):
            nazwa = request.POST.get(f'kolumna_{i}', '').strip()
            if nazwa:
                nowe.append(KolumnaAPT(numer_kolumny=i, nazwa_dzialu=nazwa))
        KolumnaAPT.objects.bulk_create(nowe)
        messages.success(request, f'Zapisano mapowanie {len(nowe)} kolumn APT.')
        kolumny = {k.numer_kolumny: k.nazwa_dzialu for k in KolumnaAPT.objects.all()}
        return render(request, 'pracownicy/import_pracownicy_apt.html', {
            'kolumny': kolumny,
            'numery_kolumn': range(1, 15),
            'apt_count': apt_count,
        })

    # Akcja: potwierdź import (synchronizacja APT: dodaj nowych, zaktualizuj istniejących, usuń usuniętych)
    if action == 'confirm':
        tmp_uuid = request.POST.get('tmp_uuid', '')
        tmp_path = _tmp_dir() / f'{tmp_uuid}.json'
        if not tmp_path.exists():
            messages.error(request, 'Sesja importu wygasła — prześlij plik ponownie.')
            return redirect('import_danych:import_pracownicy_apt')
        try:
            data = json.loads(tmp_path.read_text(encoding='utf-8'))
            counts = _zapisz_pracownikow_apt(data)
            messages.success(
                request,
                f'APT zaktualizowane: '
                f'{counts["utworzono"]} nowych, '
                f'{counts["zaktualizowano"]} zaktualizowanych, '
                f'{counts["usunieto"]} usuniętych.',
            )
        except Exception as exc:
            messages.error(request, f'Błąd zapisu: {exc}')
        finally:
            tmp_path.unlink(missing_ok=True)
        return redirect('import_danych:import_pracownicy_apt')

    # Akcja: upload — parsuj plik i pokaż podgląd pierwszych 20 pracowników
    plik = request.FILES.get('plik')
    if not plik:
        messages.error(request, 'Nie wybrano pliku.')
        return render(request, 'pracownicy/import_pracownicy_apt.html', base_ctx)

    from django.core.exceptions import ValidationError as _VE
    try:
        waliduj_plik_importu(plik)
    except _VE as exc:
        messages.error(request, exc.message)
        return render(request, 'pracownicy/import_pracownicy_apt.html', base_ctx)

    try:
        pracownicy_apt, ostrzezenia = parsuj_pracownikow_apt(plik)
    except Exception as exc:
        messages.error(request, f'Błąd parsowania pliku: {exc}')
        return render(request, 'pracownicy/import_pracownicy_apt.html', base_ctx)

    stats = {'total_pracownikow': len(pracownicy_apt)}
    data = {'pracownicy_apt': pracownicy_apt, 'ostrzezenia': ostrzezenia, 'stats': stats}

    tmp_id = str(uuid.uuid4())
    (_tmp_dir() / f'{tmp_id}.json').write_text(
        json.dumps(data, ensure_ascii=False, default=str), encoding='utf-8'
    )

    return render(request, 'pracownicy/import_pracownicy_apt.html', {
        **base_ctx,
        'podglad': pracownicy_apt[:20],
        'stats': stats,
        'ostrzezenia': ostrzezenia,
        'tmp_uuid': tmp_id,
        'nazwa_pliku': plik.name,
    })


# Synchronizuje pracowników APT: dodaje nowych, aktualizuje istniejących, usuwa usuniętych
def _zapisz_pracownikow_apt(data: dict) -> dict:
    """Sync APT workers: update existing, create new, delete removed. Returns counts."""
    incoming = data['pracownicy_apt']
    # Mapa (nazwisko, imie) → dane z importu
    incoming_map: dict[tuple, dict] = {
        (p.get('nazwisko', ''), p.get('imie', '')): p for p in incoming
    }

    # Mapa (nazwisko, imie) → obiekt DB — do porównania co dodać/zaktualizować/usunąć
    existing_map: dict[tuple, 'PracownikAPT'] = {
        (p.nazwisko, p.imie): p for p in PracownikAPT.objects.all()
    }

    # Usuń pracowników którzy nie wystąpili w nowym pliku
    to_delete_pks = [obj.pk for key, obj in existing_map.items() if key not in incoming_map]
    if to_delete_pks:
        PracownikAPT.objects.filter(pk__in=to_delete_pks).delete()

    # Zaktualizuj istniejących pracowników (agencja, płeć, grupa)
    to_update: list['PracownikAPT'] = []
    for key, obj in existing_map.items():
        if key not in incoming_map:
            continue
        pdata = incoming_map[key]
        obj.nazwa_agencji = pdata.get('nazwa_agencji', '')
        obj.plec = pdata.get('plec', '')
        obj.grupa = pdata.get('grupa', '')
        to_update.append(obj)
    if to_update:
        PracownikAPT.objects.bulk_update(to_update, ['nazwa_agencji', 'plec', 'grupa'])

    # Utwórz nowych pracowników
    new_keys = [key for key in incoming_map if key not in existing_map]
    created = PracownikAPT.objects.bulk_create([
        PracownikAPT(
            nazwisko=key[0],
            imie=key[1],
            nazwa_agencji=incoming_map[key].get('nazwa_agencji', ''),
            plec=incoming_map[key].get('plec', ''),
            grupa=incoming_map[key].get('grupa', ''),
        )
        for key in new_keys
    ])

    # Odśwież oceny: usuń stare dla zaktualizowanych, wstaw wszystkie od nowa
    updated_pks = [obj.pk for obj in to_update]
    if updated_pks:
        OcenaAPT.objects.filter(pracownik_apt_id__in=updated_pks).delete()

    oceny_objs = []
    # Oceny dla zaktualizowanych pracowników
    for obj in to_update:
        for numer_str, ocena in incoming_map[(obj.nazwisko, obj.imie)].get('oceny', {}).items():
            oceny_objs.append(OcenaAPT(
                pracownik_apt=obj,
                numer_kolumny=int(numer_str),
                ocena=float(ocena) if ocena is not None else None,
            ))
    # Oceny dla nowo utworzonych pracowników
    for obj, key in zip(created, new_keys):
        for numer_str, ocena in incoming_map[key].get('oceny', {}).items():
            oceny_objs.append(OcenaAPT(
                pracownik_apt=obj,
                numer_kolumny=int(numer_str),
                ocena=float(ocena) if ocena is not None else None,
            ))
    OcenaAPT.objects.bulk_create(oceny_objs, ignore_conflicts=True)

    return {'utworzono': len(created), 'zaktualizowano': len(to_update), 'usunieto': len(to_delete_pks)}
