import json
import math
import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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

# ── Fuzzy-matching aktywności → grupy procesowe (module-level) ────────────────
import re as _re
_ws_re = _re.compile(r'\s+')
_paren_sp_re = _re.compile(r'\s+([)\]])')
_punct_re = _re.compile(r'[^a-ząćęłńóśźż0-9\s]')


def _nrm(s: str) -> str:
    return _paren_sp_re.sub(r'\1', _ws_re.sub(' ', s.strip().lower()))


def _words(s: str) -> set:
    return set(w for w in _punct_re.sub(' ', _nrm(s)).split() if len(w) >= 3)


_GP_BY_NR: dict[int, dict] = {g['nr']: g for g in _GP}
_akt_to_group_exact: dict[str, dict] = {c: g for g in _GP for c in g['czynnosci']}
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
    """Fuzzy-match nazwy aktywności planu do grup procesowych z macierzy."""
    norm = _nrm(akt_nazwa)
    result: list[dict] = []
    seen_nrs: set[int] = set()

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
        if len(norm) >= 3 and (norm in g_norm or g_norm in norm):
            result.append(g); seen_nrs.add(g['nr']); continue
        if (len(norm_words) >= 2 and len(g_words) >= 2
                and (norm_words.issubset(g_words) or g_words.issubset(norm_words))):
            result.append(g); seen_nrs.add(g['nr']); continue
        for c in g['czynnosci']:
            c_norm = _nrm(c)
            c_words = _words(c)
            if (len(norm) >= 4 and norm in c_norm) or (len(c_norm) >= 4 and c_norm in norm):
                result.append(g); seen_nrs.add(g['nr']); break
            if (len(norm_words) >= 2 and len(c_words) >= 2
                    and (norm_words.issubset(c_words) or c_words.issubset(norm_words))):
                result.append(g); seen_nrs.add(g['nr']); break
    if not result:
        for nr in _MANUAL_MAP.get(norm, []):
            mg = _GP_BY_NR.get(nr)
            if mg:
                result.append(mg)
    return result


# ── Katalog tymczasowy dla plików podglądu importu ────────────────────────────

def _tmp_dir() -> Path:
    d = Path(settings.BASE_DIR) / 'tmp'
    d.mkdir(exist_ok=True)
    return d


def _page_range(page_obj, paginator):
    current = page_obj.number
    total = paginator.num_pages
    start = max(1, current - 3)
    end = min(total, current + 3)
    return range(start, end + 1), start, end


# ── Pracownicy ─────────────────────────────────────────────────────────────────

_ARKUSZ_KOLEJNOSC = [
    'Struktura IN', 'Struktura IB', 'Struktura OB', 'Struktura FF', 'Struktura ZW', 'Struktura PR',
]
_ARKUSZ_SKROT = {
    'Struktura IN': 'IN', 'Struktura IB': 'IB', 'Struktura OB': 'OB',
    'Struktura FF': 'FF', 'Struktura ZW': 'ZW', 'Struktura PR': 'PR',
}


@login_required
def lista(request):
    q         = request.GET.get('q', '').strip()
    arkusz_q  = request.GET.get('arkusz', '').strip()
    nieobecni = request.GET.get('nieobecni', '') == '1'

    f_nr         = request.GET.get('f_nr', '').strip()
    f_nazwisko   = request.GET.get('f_nazwisko', '').strip()
    f_imie       = request.GET.get('f_imie', '').strip()
    f_stanowisko = request.GET.get('f_stanowisko', '').strip()
    f_strefa     = request.GET.get('f_strefa', '').strip()
    f_dzial      = request.GET.get('f_dzial', '').strip()
    f_zmiana     = request.GET.get('f_zmiana', '').strip()
    f_zmiana_gr  = request.GET.get('f_zmiana_gr', '').strip()
    f_przelozony = request.GET.get('f_przelozony', '').strip()

    qs = (Pracownik.objects
          .annotate(
              liczba_kompetencji=Count('kompetencje', distinct=True),
              liczba_absencji=Count('absencje', distinct=True),
              nr_len=Length('nr_ewidencyjny'),
          )
          .prefetch_related(
              Prefetch('absencje',
                       queryset=AbsencjaPracownika.objects.order_by('data'),
                       to_attr='absencje_lista'),
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

    if q:
        qs = qs.filter(Q(nazwisko__icontains=q) | Q(imie__icontains=q))
    if arkusz_q:
        qs = qs.filter(arkusz=arkusz_q)
    if nieobecni:
        qs = qs.filter(liczba_absencji__gt=0)

    if f_nr:         qs = qs.filter(nr_ewidencyjny__icontains=f_nr)
    if f_nazwisko:   qs = qs.filter(nazwisko__icontains=f_nazwisko)
    if f_imie:       qs = qs.filter(imie__icontains=f_imie)
    if f_stanowisko: qs = qs.filter(stanowisko__icontains=f_stanowisko)
    if f_strefa:     qs = qs.filter(strefa__icontains=f_strefa)
    if f_dzial:      qs = qs.filter(dzial__icontains=f_dzial)
    if f_zmiana:     qs = qs.filter(zmiana__icontains=f_zmiana)
    if f_zmiana_gr:  qs = qs.filter(zmiana_grupa__icontains=f_zmiana_gr)
    if f_przelozony: qs = qs.filter(przelozony__icontains=f_przelozony)

    # Zakładki arkuszy z liczbą pracowników
    base_qs = Pracownik.objects
    if q:
        base_qs = base_qs.filter(Q(nazwisko__icontains=q) | Q(imie__icontains=q))
    if nieobecni:
        base_qs = base_qs.annotate(la=Count('absencje', distinct=True)).filter(la__gt=0)

    arkusze_counts = {
        row['arkusz']: row['n']
        for row in base_qs.values('arkusz').annotate(n=Count('id'))
    }
    arkusze_tabs = []
    for ark in _ARKUSZ_KOLEJNOSC:
        if ark in arkusze_counts:
            arkusze_tabs.append({
                'value': ark,
                'skrot': _ARKUSZ_SKROT.get(ark, ark),
                'count': arkusze_counts[ark],
            })
    # Pozostałe arkusze (inne niż Struktura IB/OB/FF/ZW/PR)
    for ark, cnt in arkusze_counts.items():
        if ark not in _ARKUSZ_KOLEJNOSC:
            arkusze_tabs.append({'value': ark, 'skrot': ark or 'Inne', 'count': cnt})

    from urllib.parse import urlencode
    col_filters = {
        'f_nr': f_nr, 'f_nazwisko': f_nazwisko, 'f_imie': f_imie,
        'f_stanowisko': f_stanowisko, 'f_strefa': f_strefa, 'f_dzial': f_dzial,
        'f_zmiana': f_zmiana, 'f_zmiana_gr': f_zmiana_gr, 'f_przelozony': f_przelozony,
    }
    _fp = {k: v for k, v in [
        ('q', q), ('arkusz', arkusz_q), ('nieobecni', '1' if nieobecni else ''),
        *col_filters.items(),
    ] if v}
    filter_params = urlencode(_fp)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    pr, pr_start, pr_end = _page_range(page_obj, paginator)
    return render(request, 'pracownicy/lista.html', {
        'pracownicy': page_obj,
        'q': q,
        'arkusz_q': arkusz_q,
        'nieobecni': nieobecni,
        'filter_params': filter_params,
        'arkusze_tabs': arkusze_tabs,
        'page_range': pr,
        'pr_start': pr_start,
        'pr_end': pr_end,
        **col_filters,
        'has_col_filters': any(col_filters.values()),
    })


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


@login_required
def usun_pracownika(request, pk):
    if request.method == 'POST':
        p = get_object_or_404(Pracownik, pk=pk)
        imie, nazwisko = p.imie, p.nazwisko
        p.delete()
        messages.success(request, f'Usunięto pracownika {imie} {nazwisko}.')
    return redirect('pracownicy:lista')


@login_required
def usun_wszystkich(request):
    if request.method == 'POST':
        ile = Pracownik.objects.count()
        Pracownik.objects.all().delete()
        messages.success(request, f'Usunięto {ile} pracowników.')
    return redirect('pracownicy:lista')


# ── Macierz procesowa ─────────────────────────────────────────────────────────

@login_required
def macierz_procesowa(request):
    from .grupy_procesowe import GRUPY_PROCESOWE

    tryb = request.GET.get('tryb', 'ranking')  # 'ranking' | 'mapowanie'

    # Wszystkie aktywności z DB (indeks po nazwie)
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
        for nazwa in czynnosci_pdf:
            pk = db_aktywnosci.get(nazwa)
            if pk:
                matched_ids.append(pk)
                matched_names.append(nazwa)
                total_matched += 1
            else:
                unmatched_names.append(nazwa)

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

@login_required
def plany_lista(request):
    plany = (
        PlanDzienny.objects
        .annotate(
            total_aktywnosci=Count('zapotrzebowania__aktywnosc', distinct=True),
            total_rekordow=Count('zapotrzebowania'),
        )
        .select_related('przydzial')
        .order_by('-data_importu')
    )
    return render(request, 'pracownicy/plany_lista.html', {'plany': plany})


@login_required
def usun_plan(request, pk):
    if request.method == 'POST':
        plan = get_object_or_404(PlanDzienny, pk=pk)
        nazwa = plan.nazwa_pliku
        plan.delete()
        messages.success(request, f'Usunięto plan: {nazwa}.')
    return redirect('pracownicy:plany_lista')


# ── Lista pracowników APT ──────────────────────────────────────────────────────

# ── Przydział pracowników do planu ────────────────────────────────────────────

_PRIORITY_DEPTS = frozenset({'IN', 'OB', 'FF', 'ZW', 'PR'})

# Słowa kluczowe dla każdego kodu departamentu — dopasowywane do Aktywnosc.dzial z planu
_DEPT_KEYWORDS: dict[str, list[str]] = {
    'IN': ['in', 'ib', 'inbound', 'przej', 'odbi'],
    'OB': ['ob', 'outbound', 'ekspedy', 'wysy'],
    'FF': ['ff', 'fulfil', 'kompl'],
    'ZW': ['zw', 'zwrot', 'return'],
    'PR': ['pr', 'prasa', 'press'],
}


def _norm(s: str) -> str:
    return s.strip().lower() if s else ''


def _dzialy_match(dzial_p: str, dzial_a: str) -> bool:
    a, b = _norm(dzial_p), _norm(dzial_a)
    return bool(a and b and (a in b or b in a))


def _dept_matches_akt(departament: str, dzial_a: str) -> bool:
    """Dopasuj kod departamentu (IN/OB/FF/ZW/PR) do nazwy działu z planu."""
    keywords = _DEPT_KEYWORDS.get(departament.strip().upper(), [])
    z = _norm(dzial_a)
    return bool(z and any(kw in z or z.startswith(kw) for kw in keywords))


def _dept_for_dzial(dzial: str) -> str:
    """Zwróć kod strefy (IN/OB/FF/ZW/PR) dla nazwy działu z planu, lub '' jeśli brak."""
    z = _norm(dzial)
    for dept, keywords in _DEPT_KEYWORDS.items():
        if any(kw in z or z.startswith(kw) for kw in keywords):
            return dept
    return ''


def _pasuje_do_aktywnosci(p, akt_nazwa_norm: str, akt_dzial: str) -> bool:
    """True jeśli pracownik pasuje do aktywności przez dowolne kryterium."""
    return (
        _norm(p.stanowisko) == akt_nazwa_norm
        or _dzialy_match(p.dzial, akt_dzial)
        or _dept_matches_akt(p.departament, akt_dzial)
    )


def _wykonaj_przydzial(plan: PlanDzienny) -> dict:
    """
    Plan-driven assignment based on ZapotrzebowanieGodzinowe.

    Dla każdej (aktywność, zmiana) z planu:
      capacity = ceil(max godzinowego zapotrzebowania)
    Kolejność wypełniania do capacity:
      1. Pracownicy Struktura z pasującym stanowiskiem/działem/departamentem/kompetencją
         — wewnątrz grupy: najpierw ci z oceną w grupie procesowej (malejąco), potem reszta
      2. Pracownicy APT wg ocen
    Priorytetowi bez dopasowania → force-assign do pierwszej aktywności z ich działu.
    Wynik zawiera 'godziny': {godzina_str: liczba_wymagana} dla rozbicia godzinowego.
    """
    # 1. Wczytaj zapotrzebowanie godzinowe dla planu
    zap_qs = (ZapotrzebowanieGodzinowe.objects
              .filter(plan=plan)
              .select_related('aktywnosc'))

    plan_godziny: dict[tuple, dict[int, float]] = {}   # (akt_pk, zmiana) → {h: osob}
    for zap in zap_qs:
        key = (zap.aktywnosc_id, zap.zmiana)
        plan_godziny.setdefault(key, {})[zap.godzina] = zap.liczba_osob

    if not plan_godziny:
        return {}

    akt_pks_in_plan = {k[0] for k in plan_godziny}
    akt_cache = {a.pk: a for a in Aktywnosc.objects.filter(pk__in=akt_pks_in_plan)}

    # 2. Pracownicy Struktura
    pracownicy = list(Pracownik.objects.all())
    pk_to_p = {p.pk: p for p in pracownicy}

    # Zbiór PK pracowników nieobecnych w dniu planu
    nieobecni_pks: set[int] = set()
    if plan.data_planu:
        nieobecni_pks = set(
            AbsencjaPracownika.objects
            .filter(data=plan.data_planu)
            .values_list('pracownik_id', flat=True)
        )

    # Mapa kompetencji pracowników: pracownik_pk → set(aktywnosc_pk z wynikiem > 0)
    komp_map: dict[int, set[int]] = {}
    for k in KompetencjaPracownika.objects.filter(aktywnosc_id__in=akt_pks_in_plan, wynik__gt=0):
        komp_map.setdefault(k.pracownik_id, set()).add(k.aktywnosc_id)

    # --- Macierz procesowa: oceny pracowników wg grup procesowych ---
    # Dla każdej aktywności z planu: fuzzy-match do grup procesowych,
    # zbierz PKi wszystkich czynności z dopasowanych grup.
    _nazwa_to_pk = {a.nazwa: a.pk for a in Aktywnosc.objects.only('pk', 'nazwa')}
    akt_grupa_pks: dict[int, set[int]] = {}
    for akt_pk in akt_pks_in_plan:
        akt = akt_cache[akt_pk]
        groups = _find_all_groups(akt.nazwa)
        group_czynnosci = [c for g in groups for c in g['czynnosci']]
        akt_grupa_pks[akt_pk] = {_nazwa_to_pk[n] for n in group_czynnosci if n in _nazwa_to_pk}

    # Oblicz średnią ocenę pracownika dla każdej aktywności planu (przez grupę procesową)
    # worker_group_score[(worker_pk, plan_akt_pk)] = avg wynik w grupie procesowej
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
        # indeks: aktywnosc_pk → set of plan_akt_pks które mają tę aktywność w grupie
        group_pk_to_plan_akt: dict[int, set[int]] = {}
        for plan_akt_pk, group_pks in akt_grupa_pks.items():
            for gpk in group_pks:
                group_pk_to_plan_akt.setdefault(gpk, set()).add(plan_akt_pk)
        # Akumuluj sumy i liczby per (worker, plan_akt)
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

    # 3. Pracownicy APT + mapowanie ocen na aktywności
    apt_pracownicy = list(PracownikAPT.objects.prefetch_related('oceny'))
    kolumna_map = {k.numer_kolumny: k.nazwa_dzialu for k in KolumnaAPT.objects.all()}
    akt_by_norm_nazwa = {_norm(a.nazwa): a for a in akt_cache.values()}

    comp_apt: dict[tuple, float] = {}
    for apt in apt_pracownicy:
        for ocena in apt.oceny.all():
            if ocena.ocena is None or ocena.ocena <= 0:
                continue
            nazwa_dzialu = kolumna_map.get(ocena.numer_kolumny, '')
            if not nazwa_dzialu:
                continue
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

    result: dict = {}

    globally_assigned_prac: set[int] = set()
    globally_assigned_apt: set[int] = set()

    litera_map = KonfiguracjaZmian.pobierz().jako_slownik()

    for zmiana in (1, 2, 3):
        litera = litera_map[zmiana]

        # Aktywności tej zmiany z pojemnością > 0; sortuj od największego zapotrzebowania
        shift_acts: list[tuple] = []   # (akt_pk, capacity, godziny_dict)
        for akt_pk in sorted(akt_pks_in_plan):
            g = plan_godziny.get((akt_pk, zmiana))
            if not g:
                continue
            max_wymagane = max(g.values(), default=0.0)
            if max_wymagane <= 0:
                continue
            shift_acts.append((akt_pk, math.ceil(max_wymagane), g))
        shift_acts.sort(key=lambda x: -x[1])

        def _w_tej_zmianie(p) -> bool:
            zg = p.zmiana_grupa.upper() if p.zmiana_grupa else ''
            return zg.startswith(litera) or (not zg and p.pk not in globally_assigned_prac)

        unassigned_priority: set[int] = {
            p.pk for p in pracownicy
            if _w_tej_zmianie(p) and p.departament.upper() in _PRIORITY_DEPTS
        }
        unassigned_others: set[int] = {
            p.pk for p in pracownicy
            if _w_tej_zmianie(p) and p.departament.upper() not in _PRIORITY_DEPTS
        }

        def _apt_w_tej_zmianie(apt) -> bool:
            zg = apt.grupa.upper() if apt.grupa else ''
            return zg.startswith(litera) or (not zg and apt.pk not in globally_assigned_apt)

        unassigned_apt: set[int] = {
            apt.pk for apt in apt_pracownicy if _apt_w_tej_zmianie(apt)
        }

        akt_assignments: dict[int, list[dict]] = {}
        akt_meta: dict[int, tuple] = {}
        for akt_pk, capacity, godziny in shift_acts:
            akt_assignments[akt_pk] = []
            akt_meta[akt_pk] = (capacity, godziny)

        shift_akt_pks = {akt_pk for akt_pk, _, _ in shift_acts}

        # --- Faza 1: pre-rezerwacja wg macierzy procesowej ---
        # Każdy pracownik ze scorami idzie do aktywności, gdzie ma NAJWYŻSZY wynik.
        # Najlepsi pracownicy są obsługiwani pierwsi (sort po best_score desc),
        # więc "gwiazdy" zajmują swoje optymalne miejsce zanim trafi je ktoś słabszy.
        worker_best: dict[int, tuple[float, int]] = {}  # wpk → (best_score, best_akt_pk)
        for wpk in (unassigned_priority | unassigned_others):
            best_score = 0.0
            best_akt = -1
            for apk in shift_akt_pks:
                s = worker_group_score.get((wpk, apk), 0.0)
                if s > best_score:
                    best_score, best_akt = s, apk
            if best_akt != -1 and best_score > 0:
                worker_best[wpk] = (best_score, best_akt)

        for wpk, (score, akt_pk) in sorted(worker_best.items(), key=lambda x: -x[1][0]):
            capacity = akt_meta[akt_pk][0]
            assigned = akt_assignments[akt_pk]
            if len(assigned) >= capacity:
                continue
            obj = pk_to_p[wpk]
            assigned.append({'pk': wpk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                             'zmiana_grupa': obj.zmiana_grupa,
                             'nieobecny': wpk in nieobecni_pks,
                             'wynik': round(score, 1),
                             'zapychacz': False, 'apt': False})
            unassigned_priority.discard(wpk)
            unassigned_others.discard(wpk)

        # --- Faza 2: uzupełnienie pozostałej pojemności wg standardowego dopasowania ---
        for akt_pk, capacity, godziny in shift_acts:
            akt = akt_cache[akt_pk]
            assigned = akt_assignments[akt_pk]
            norm_nazwa = _norm(akt.nazwa)
            akt_dzial = akt.dzial

            if len(assigned) < capacity:
                combined = unassigned_priority | unassigned_others
                candidates = [p for p in combined
                              if (_pasuje_do_aktywnosci(pk_to_p[p], norm_nazwa, akt_dzial)
                                  or akt_pk in komp_map.get(p, set())
                                  or worker_group_score.get((p, akt_pk), 0.0) > 0)]
                candidates.sort(key=lambda p: (
                    -worker_group_score.get((p, akt_pk), 0.0),
                    0 if p in unassigned_priority else 1,
                    pk_to_p[p].nazwisko,
                ))
                for pk in candidates[:capacity - len(assigned)]:
                    obj = pk_to_p[pk]
                    score2 = worker_group_score.get((pk, akt_pk))
                    assigned.append({'pk': pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                                     'zmiana_grupa': obj.zmiana_grupa,
                                     'nieobecny': pk in nieobecni_pks,
                                     'wynik': round(score2, 1) if score2 else None,
                                     'zapychacz': False, 'apt': False})
                    unassigned_priority.discard(pk)
                    unassigned_others.discard(pk)

            # APT: sortuj wg oceny dla tej aktywności malejąco
            apt_by_score = sorted(unassigned_apt,
                                  key=lambda pk: -comp_apt.get((pk, akt_pk), 0.0))
            for apt_pk2 in apt_by_score[:capacity - len(assigned)]:
                obj = apt_pk_to_p[apt_pk2]
                assigned.append({'pk': apt_pk2, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                                  'zmiana_grupa': obj.grupa,
                                  'nieobecny': False,
                                  'wynik': None, 'zapychacz': False, 'apt': True})
                unassigned_apt.discard(apt_pk2)

        # Force-assign: priorytetowi, którym nie przydzielono aktywności
        for pk in list(unassigned_priority):
            obj = pk_to_p[pk]
            for akt_pk, _, _ in shift_acts:
                akt_dzial_fa = akt_cache[akt_pk].dzial
                if (_dzialy_match(obj.dzial, akt_dzial_fa)
                        or _dept_matches_akt(obj.departament, akt_dzial_fa)
                        or akt_pk in komp_map.get(pk, set())):
                    akt_assignments.setdefault(akt_pk, []).append({
                        'pk': pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                        'zmiana_grupa': obj.zmiana_grupa,
                        'nieobecny': pk in nieobecni_pks,
                        'wynik': None, 'zapychacz': False, 'apt': False,
                    })
                    unassigned_priority.discard(pk)
                    break

        # Zbuduj wynik zmiany
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

        # Fillers
        fillers: list[dict] = []
        for pk in (*unassigned_priority, *unassigned_others):
            obj = pk_to_p[pk]
            fillers.append({'pk': pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                            'zmiana_grupa': obj.zmiana_grupa,
                            'nieobecny': pk in nieobecni_pks,
                            'wynik': None, 'zapychacz': True, 'apt': False})
        for apt_pk in unassigned_apt:
            obj = apt_pk_to_p[apt_pk]
            fillers.append({'pk': apt_pk, 'imie': obj.imie, 'nazwisko': obj.nazwisko,
                            'zmiana_grupa': obj.grupa,
                            'nieobecny': False,
                            'wynik': None, 'zapychacz': True, 'apt': True})
        if fillers:
            zmiana_result['__fillers__'] = {
                'nazwa': '(bez przypisanej aktywności)',
                'dzial': '',
                'wymagana': len(fillers),
                'pracownicy': sorted(fillers, key=lambda w: (w['nazwisko'], w['imie'])),
                'godziny': {},
            }

        # Rejestruj globalnie przydzielonych (deduplication dla "bez zmiany")
        for workers_list in akt_assignments.values():
            for w in workers_list:
                if w.get('apt'):
                    globally_assigned_apt.add(w['pk'])
                else:
                    globally_assigned_prac.add(w['pk'])

        result[str(zmiana)] = zmiana_result

    return result


@login_required
def przydziel_plan(request, pk):
    if request.method != 'POST':
        return redirect('pracownicy:plany_lista')
    plan = get_object_or_404(PlanDzienny, pk=pk)
    if not Pracownik.objects.exists():
        messages.error(request, 'Brak pracowników w bazie — najpierw zaimportuj pracowników.')
        return redirect('pracownicy:plany_lista')
    try:
        dane = _wykonaj_przydzial(plan)
        PrzydzialDzienny.objects.update_or_create(plan=plan, defaults={'dane': dane})
        messages.success(request, f'Przydzielono pracowników do planu „{plan.nazwa_pliku}".')
    except Exception as exc:
        messages.error(request, f'Błąd przydziału: {exc}')
        return redirect('pracownicy:plany_lista')
    return redirect('pracownicy:wyniki_przydzialu', pk=pk)


ZMIANA_NAZWA = {1: 'Zmiana I (6–13)', 2: 'Zmiana II (14–21)', 3: 'Zmiana III (22–5)'}


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
            akt_data['kompletny'] = (n >= akt_data.get('wymagana', n))

            if akt_key == '__fillers__':
                akt_data['dzial'] = ''
                total_fillers += n
                dzialy_org.setdefault('(bez przypisanej aktywności)', []).append(akt_data)
            else:
                dzial = akt_data['dzial'] or '(bez działu)'
                dzialy_org.setdefault(dzial, []).append(akt_data)
                total_pracownicy += n

        for lst in dzialy_org.values():
            lst.sort(key=lambda x: x['nazwa'])

        # Move fillers section to end
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

    _zmiana_godziny = {
        1: [6, 7, 8, 9, 10, 11, 12, 13],
        2: [14, 15, 16, 17, 18, 19, 20, 21],
        3: [22, 23, 0, 1, 2, 3, 4, 5],
    }
    # Dodaj godziny_ordered (lista [[h, wymagane], ...]) do każdej aktywności
    for zmiana_int, zd in zmiany_dane.items():
        hour_order = _zmiana_godziny.get(zmiana_int, [])
        for aktywnosci in zd['dzialy'].values():
            for akt_data in aktywnosci:
                g = akt_data.get('godziny') or {}
                akt_data['godziny_ordered'] = [
                    [h, g.get(str(h), 0.0)] for h in hour_order
                ]

    # Mapowanie nazwa_działu → kod strefy (IN/OB/FF/ZW/PR)
    all_dzialy: set[str] = set()
    for zd in zmiany_dane.values():
        all_dzialy.update(zd['dzialy'].keys())
    dzial_dept = {d: _dept_for_dzial(d) for d in all_dzialy}

    litera_map = KonfiguracjaZmian.pobierz().jako_slownik()

    # --- Dane do modali aktywności i pracowników ---
    _db_akt_names = set(Aktywnosc.objects.values_list('nazwa', flat=True))

    # Zbierz PKi WSZYSTKICH pracowników z planu (strukturowych, nie APT)
    all_plan_worker_pks: set[int] = set()
    for _zd in zmiany_dane.values():
        for _akts in _zd['dzialy'].values():
            for _akt in _akts:
                for _p in _akt.get('pracownicy', []):
                    if not _p.get('apt'):
                        all_plan_worker_pks.add(_p['pk'])

    # Top 4 kompetencje per pracownik (posortowane wg wyniku desc)
    worker_top_komp: dict[int, list[dict]] = {}
    if all_plan_worker_pks:
        _komp_rows = (KompetencjaPracownika.objects
                      .filter(pracownik_id__in=all_plan_worker_pks, wynik__gt=0)
                      .select_related('aktywnosc')
                      .order_by('pracownik_id', '-wynik'))
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

    # worker_data: pk → {imie, nazwisko, zmiana_grupa, wynik_procesowy, top_komp}
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

    def _groups_to_info(groups: list[dict]) -> list[dict]:
        return [
            {
                'nr': _g['nr'],
                'nazwa': _g['nazwa'],
                'czynnosci': [
                    {'nazwa': _c, 'w_db': _c in _db_akt_names}
                    for _c in _g['czynnosci']
                ],
            }
            for _g in groups
        ]

    # modal_data: nazwa_aktywności → {groups, workers_scored}
    modal_data: dict[str, dict] = {}
    _seen: set[str] = set()
    for _zd in zmiany_dane.values():
        for _akts in _zd['dzialy'].values():
            for _akt in _akts:
                _nazwa = _akt.get('nazwa', '')
                if not _nazwa or _nazwa == '(bez przypisanej aktywności)' or _nazwa in _seen:
                    continue
                _seen.add(_nazwa)
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

    # Rankingi w grupach procesowych dla wszystkich pracowników planu
    _db_akt_pk_map = {a.nazwa: a.pk for a in Aktywnosc.objects.only('pk', 'nazwa')}
    _gpk_to_g: dict[int, dict] = {}
    for _g in _GP:
        for _c in _g['czynnosci']:
            _pk2 = _db_akt_pk_map.get(_c)
            if _pk2:
                _gpk_to_g[_pk2] = _g

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

    # ranking per grupa: nr → [(wpk, avg)] malejąco
    _grp_rankings: dict[int, list] = {}
    for (_wpk2, _gnr), _s in _wpk_grp_sums.items():
        _avg2 = round(_s / _wpk_grp_cnts[(_wpk2, _gnr)], 1)
        _grp_rankings.setdefault(_gnr, []).append((_wpk2, _avg2))
    for _gnr in _grp_rankings:
        _grp_rankings[_gnr].sort(key=lambda x: -x[1])

    _grp_info_map = {_g['nr']: _g for _g in _GP}
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
    for _wpk2 in _worker_grp_ranks:
        _worker_grp_ranks[_wpk2].sort(key=lambda x: -x['score'])

    # Dołącz rankingi do worker_data
    for _wpk2, _wdata in worker_data.items():
        _wdata['group_rankings'] = _worker_grp_ranks.get(_wpk2, [])

    # dzial_modal_data: nazwa_działu → {groups: [{nr, nazwa, czynnosci}]}
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
        'zmiany_dane': dict(sorted(zmiany_dane.items())),
        'dzial_dept': dzial_dept,
        'litera_map': litera_map,
        'modal_data_json': json.dumps(modal_data, ensure_ascii=False),
        'worker_data_json': json.dumps(
            {str(pk): v for pk, v in worker_data.items()}, ensure_ascii=False
        ),
        'dzial_data_json': json.dumps(dzial_modal_data, ensure_ascii=False),
    })


# ── Lista pracowników APT ──────────────────────────────────────────────────────

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

@login_required
def import_plan_zmianowy(request):
    plany_count = PlanDzienny.objects.count()

    if request.method == 'GET':
        return render(request, 'pracownicy/import_plan_zmianowy.html', {
            'plany_count': plany_count,
            'konfig_zmian': KonfiguracjaZmian.pobierz(),
        })

    action = request.POST.get('action', 'upload')

    if action == 'save_config':
        cfg = KonfiguracjaZmian.pobierz()
        z1 = request.POST.get('zmiana_1', 'A')
        z2 = request.POST.get('zmiana_2', 'B')
        z3 = request.POST.get('zmiana_3', 'C')
        valid = {'A', 'B', 'C'}
        if z1 in valid and z2 in valid and z3 in valid and len({z1, z2, z3}) == 3:
            cfg.zmiana_1, cfg.zmiana_2, cfg.zmiana_3 = z1, z2, z3
            cfg.save()
            messages.success(request, f'Konfiguracja zmian zapisana: I={z1}, II={z2}, III={z3}.')
        else:
            messages.error(request, 'Nieprawidłowa konfiguracja — każda litera (A/B/C) musi być użyta dokładnie raz.')
        return redirect('import_danych:import_plan_zmianowy')

    if action == 'confirm':
        tmp_uuid = request.POST.get('tmp_uuid', '')
        tmp_path = _tmp_dir() / f'{tmp_uuid}.json'
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
            tmp_path.unlink(missing_ok=True)

        s = data['stats']
        messages.success(
            request,
            f'Zaimportowano plan „{s["nazwa_pliku"]}": '
            f'{s["total_aktywnosci"]} aktywności, '
            f'{s["total_rekordow"]} rekordów godzinowych.',
        )
        return redirect('pracownicy:plany_lista')

    # action == 'upload'
    data_planu_raw = request.POST.get('data_planu', '').strip()
    plik = request.FILES.get('plik')
    if not plik:
        messages.error(request, 'Nie wybrano pliku.')
        return render(request, 'pracownicy/import_plan_zmianowy.html', {
            'plany_count': plany_count,
        })

    if not plik.name.lower().endswith('.xlsx'):
        messages.error(request, 'Wymagany format: .xlsx')
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

    dzialy: dict[str, int] = {}
    for w in wiersze:
        dzialy[w.dzial] = dzialy.get(w.dzial, 0) + 1

    stats = {
        'nazwa_pliku': plik.name,
        'total_aktywnosci': len(wiersze),
        'total_rekordow': len(wiersze) * 24,
        'dzialy': dzialy,
    }

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

    tmp_id = str(uuid.uuid4())
    (_tmp_dir() / f'{tmp_id}.json').write_text(
        json.dumps(data, ensure_ascii=False), encoding='utf-8'
    )

    return render(request, 'pracownicy/import_plan_zmianowy.html', {
        'podglad': wiersze[:40],
        'stats': stats,
        'ostrzezenia': ostrzezenia,
        'tmp_uuid': tmp_id,
        'nazwa_pliku': plik.name,
        'data_planu': data_planu_raw,
        'plany_count': plany_count,
    })


def _zapisz_plan_dzienny(data: dict, user) -> None:
    from datetime import date as date_type
    raw = data.get('data_planu', '')
    try:
        dp = date_type.fromisoformat(raw) if raw else None
    except ValueError:
        dp = None
    plan = PlanDzienny.objects.create(
        nazwa_pliku=data['stats']['nazwa_pliku'],
        data_planu=dp,
        importowany_przez=user,
    )
    aktywnosci_cache: dict[tuple, int] = {}
    rekordy = []

    for wpis in data['wiersze']:
        key = (wpis['aktywnosc'], wpis['dzial'])
        if key not in aktywnosci_cache:
            akt, _ = Aktywnosc.objects.get_or_create(nazwa=wpis['aktywnosc'], dzial=wpis['dzial'])
            aktywnosci_cache[key] = akt.pk

        akt_pk = aktywnosci_cache[key]
        wolumeny = {1: wpis['wolumen_I'], 2: wpis['wolumen_II'], 3: wpis['wolumen_III']}

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

    ZapotrzebowanieGodzinowe.objects.bulk_create(rekordy, ignore_conflicts=True)


# ── Import: pracownicy ─────────────────────────────────────────────────────────

@login_required
def import_pracownicy(request):
    pracownicy_count = Pracownik.objects.count()

    if request.method == 'GET':
        return render(request, 'pracownicy/import_pracownicy.html', {
            'pracownicy_count': pracownicy_count,
        })

    action = request.POST.get('action', 'upload')

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

    # action == 'upload'
    plik_kompetencje = request.FILES.get('plik_kompetencje')
    plik_struktura = request.FILES.get('plik_struktura')

    if not plik_kompetencje and not plik_struktura:
        messages.error(request, 'Wybierz co najmniej jeden plik.')
        return render(request, 'pracownicy/import_pracownicy.html', {
            'pracownicy_count': pracownicy_count,
        })

    pracownicy_dict: dict[tuple, dict] = {}
    kompetencje_dict: dict[tuple, list] = {}
    absencje_list: list[dict] = []
    ostrzezenia: list[str] = []

    if plik_kompetencje:
        if not plik_kompetencje.name.lower().endswith('.xlsx'):
            messages.error(request, 'Plik kompetencji musi być .xlsx')
            return render(request, 'pracownicy/import_pracownicy.html', {
                'pracownicy_count': pracownicy_count,
            })
        try:
            p_list, k_dict, ostr = parsuj_kompetencje(plik_kompetencje)
            for p in p_list:
                key = (p['nazwisko'], p['imie'])
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
        if not plik_struktura.name.lower().endswith('.xlsx'):
            messages.error(request, 'Plik struktury musi być .xlsx')
            return render(request, 'pracownicy/import_pracownicy.html', {
                'pracownicy_count': pracownicy_count,
            })
        try:
            p_list, a_list, ostr = parsuj_strukture(plik_struktura)
            for p in p_list:
                key = (p['nazwisko'], p['imie'])
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

    pracownicy_list = [
        {**pdata, 'kompetencje': kompetencje_dict.get(key, [])}
        for key, pdata in pracownicy_dict.items()
    ]

    stats = {
        'total_pracownikow': len(pracownicy_list),
        'total_kompetencji': sum(len(p['kompetencje']) for p in pracownicy_list),
        'total_absencji': len(absencje_list),
    }

    # Grupowanie per arkusz do podglądu w modalu
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
                'pracownicy': arkusze[sh][:40],
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


def _zapisz_pracownikow(data: dict) -> None:
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
        # Normalizacja: jeśli grupa to sama cyfra (np. "2") a zmiana to litera → "C-2"
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

    created = Pracownik.objects.bulk_create(nowi)
    pk_by_name: dict[tuple, int] = {(p.imie, p.nazwisko): p.pk for p in created}

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

    abs_objs = []
    for a in data['absencje']:
        klucz = a.get('pracownik_klucz', '')
        if '|' not in klucz:
            continue
        nazwisko, imie = klucz.split('|', 1)
        pk = pk_by_name.get((imie, nazwisko))
        if pk is None:
            continue
        try:
            d = date.fromisoformat(a['data'][:10])
        except (ValueError, KeyError):
            continue
        abs_objs.append(AbsencjaPracownika(pracownik_id=pk, data=d, typ=a['typ']))
    AbsencjaPracownika.objects.bulk_create(abs_objs, ignore_conflicts=True)


# ── Import: pracownicy APT ─────────────────────────────────────────────────────

@login_required
def import_pracownicy_apt(request):
    kolumny = {k.numer_kolumny: k.nazwa_dzialu for k in KolumnaAPT.objects.all()}
    apt_count = PracownikAPT.objects.count()
    base_ctx = {'kolumny': kolumny, 'numery_kolumn': range(1, 15), 'apt_count': apt_count}

    if request.method == 'GET':
        return render(request, 'pracownicy/import_pracownicy_apt.html', base_ctx)

    action = request.POST.get('action', 'upload')

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

    # action == 'upload'
    plik = request.FILES.get('plik')
    if not plik:
        messages.error(request, 'Nie wybrano pliku.')
        return render(request, 'pracownicy/import_pracownicy_apt.html', base_ctx)

    if not plik.name.lower().endswith('.xlsx'):
        messages.error(request, 'Wymagany format: .xlsx')
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


def _zapisz_pracownikow_apt(data: dict) -> dict:
    """Sync APT workers: update existing, create new, delete removed. Returns counts."""
    incoming = data['pracownicy_apt']
    incoming_map: dict[tuple, dict] = {
        (p.get('nazwisko', ''), p.get('imie', '')): p for p in incoming
    }

    existing_map: dict[tuple, 'PracownikAPT'] = {
        (p.nazwisko, p.imie): p for p in PracownikAPT.objects.all()
    }

    # Delete workers absent in new file
    to_delete_pks = [obj.pk for key, obj in existing_map.items() if key not in incoming_map]
    if to_delete_pks:
        PracownikAPT.objects.filter(pk__in=to_delete_pks).delete()

    # Update existing
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

    # Create new
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

    # Refresh scores: delete old for updated workers, insert all fresh
    updated_pks = [obj.pk for obj in to_update]
    if updated_pks:
        OcenaAPT.objects.filter(pracownik_apt_id__in=updated_pks).delete()

    oceny_objs = []
    for obj in to_update:
        for numer_str, ocena in incoming_map[(obj.nazwisko, obj.imie)].get('oceny', {}).items():
            oceny_objs.append(OcenaAPT(
                pracownik_apt=obj,
                numer_kolumny=int(numer_str),
                ocena=float(ocena) if ocena is not None else None,
            ))
    for obj, key in zip(created, new_keys):
        for numer_str, ocena in incoming_map[key].get('oceny', {}).items():
            oceny_objs.append(OcenaAPT(
                pracownik_apt=obj,
                numer_kolumny=int(numer_str),
                ocena=float(ocena) if ocena is not None else None,
            ))
    OcenaAPT.objects.bulk_create(oceny_objs, ignore_conflicts=True)

    return {'utworzono': len(created), 'zaktualizowano': len(to_update), 'usunieto': len(to_delete_pks)}
