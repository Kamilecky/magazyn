import os
import sys
import csv
import io
import json
import openpyxl
from django.utils import timezone
import io
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from openai import OpenAI, APIError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Pracownik, PlanZmiany

# ── Prompty AI ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    'Jesteś asystentem systemu magazynowego. Otrzymasz zawartość pliku Excel lub CSV '
    'z listą pracowników. Wiersze oddzielone są znakiem | .\n\n'
    'Twoim zadaniem jest:\n'
    '1. Zidentyfikować kolumny zawierające imię i nazwisko każdego pracownika.\n'
    '   Kolumny mogą mieć dowolne nazwy i kolejność (np. "Imię", "Name", "Pracownik" itp.)\n'
    '2. Zidentyfikować kolumny zawierające doświadczenie lub kwalifikacje pracownika.\n'
    '   Mogą to być kolumny o nazwach: "Doświadczenie", "Stanowisko", "Kwalifikacje", "Umiejętności",\n'
    '   "Dział", skróty nazw stanowisk itp.\n'
    '   Przepisuj wartości dokładnie tak jak są — nie normalizuj, nie pomijaj.\n'
    '   Jeśli pracownik ma wiele pozycji doświadczenia (kilka kolumn lub wartości po przecinku),\n'
    '   zwróć wszystkie jako osobne elementy listy.\n'
    '   Jeśli brak danych o doświadczeniu — zwróć pustą listę [].\n\n'
    'WAŻNE: Przetwórz KAŻDY wiersz z danymi — nie pomijaj żadnego, nawet jeśli dane są niekompletne.\n'
    'Pomiń wyłącznie wiersze nagłówkowe (zawierające nazwy kolumn) oraz całkowicie puste wiersze.\n'
    'Liczba elementów w tablicy wynikowej musi być równa liczbie wierszy z danymi pracowników.\n\n'
    'Zwróć WYŁĄCZNIE tablicę JSON, bez żadnego wstępu, komentarza ani znaczników markdown.\n'
    'Format każdego elementu:\n'
    '{"imie": "...", "nazwisko": "...", "doswiadczenie": ["...", "..."]}\n\n'
    'Przykład poprawnej odpowiedzi:\n'
    '[\n'
    '  {"imie": "Jan", "nazwisko": "Kowalski", "doswiadczenie": ["PTS 4", "Wózek - Retrack"]},\n'
    '  {"imie": "Anna", "nazwisko": "Nowak", "doswiadczenie": ["PTS 10"]},\n'
    '  {"imie": "Marek", "nazwisko": "Wiśniewski", "doswiadczenie": []}\n'
    ']'
)

SYSTEM_PROMPT_PLAN = (
    'Jesteś asystentem systemu magazynowego. Otrzymasz zawartość pliku Excel\n'
    'z planem pracy na zmianę (dzienną lub nocną). Wiersze oddzielone są znakiem | .\n\n'
    'Twoim zadaniem jest zidentyfikowanie każdego stanowiska pracy i wymaganej liczby pracowników (obsady).\n\n'
    'Plik może mieć różne formaty:\n'
    '1. Kolumna "Stanowisko" i kolumna "Obsada" / "Liczba" / "Ilość" — czytaj bezpośrednio.\n'
    '2. Lista wierszy z pracownikami przypisanymi do stanowisk — policz ilu pracowników\n'
    '   jest przypisanych do każdego stanowiska i to jest obsada.\n'
    '3. Tabela z nazwami stanowisk w nagłówkach i liczbą pod spodem — czytaj odpowiednio.\n\n'
    'Każde stanowisko powinno wystąpić tylko raz w wynikowej tablicy.\n'
    'Pomiń wiersze nagłówkowe, puste stanowiska oraz stanowiska z obsadą 0.\n'
    'Przepisuj nazwy stanowisk dokładnie tak jak są w pliku.\n\n'
    'Zwróć WYŁĄCZNIE tablicę JSON, bez żadnego wstępu, komentarza ani znaczników markdown.\n'
    'Format każdego elementu:\n'
    '{"stanowisko": "...", "obsada": N}\n\n'
    'Przykład poprawnej odpowiedzi:\n'
    '[\n'
    '  {"stanowisko": "PTS 10", "obsada": 7},\n'
    '  {"stanowisko": "PTS 4", "obsada": 5},\n'
    '  {"stanowisko": "Sorter - Wrzucanie", "obsada": 3}\n'
    ']'
)

# ── Helpery ───────────────────────────────────────────────────────────────────

def _excel_na_tekst(plik):
    wb = openpyxl.load_workbook(plik, data_only=True)
    ws = wb.active
    wiersze = []
    for row in ws.iter_rows(values_only=True):
        if any(cell is not None for cell in row):
            wiersze.append(' | '.join('' if cell is None else str(cell) for cell in row))
    return '\n'.join(wiersze)


def _csv_na_tekst(plik):
    content = plik.read().decode('utf-8-sig', errors='replace')
    reader = csv.reader(io.StringIO(content))
    wiersze = []
    for row in reader:
        if any(cell.strip() for cell in row):
            wiersze.append(' | '.join(cell.strip() for cell in row))
    return '\n'.join(wiersze)


def _wywolaj_openai(tekst_pliku, nazwa_pliku='plik', system_prompt=SYSTEM_PROMPT, max_tokens=8192):
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
    odpowiedz = client.chat.completions.create(
        model='gpt-4o-mini',
        max_tokens=max_tokens,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'Oto zawartość pliku: {nazwa_pliku}\n\n{tekst_pliku}'},
        ],
    )
    tekst = odpowiedz.choices[0].message.content.strip()
    if tekst.startswith('```'):
        tekst = '\n'.join(l for l in tekst.split('\n') if not l.startswith('```')).strip()
    return json.loads(tekst)


def _wykonaj_dopasowanie(plan):
    """Przypisuje pracowników z pasującym doswiadczenie do stanowisk z planu (bez podwójnego przypisania)."""
    pracownicy = list(Pracownik.objects.all())
    przypisane_idx = set()
    wyniki = {}

    for wpis in (plan.dane_raw or []):
        stanowisko = (wpis.get('stanowisko') or '').strip()
        obsada = int(wpis.get('obsada') or 0)
        if not stanowisko or obsada <= 0:
            continue

        przypisani = []
        for i, p in enumerate(pracownicy):
            if i in przypisane_idx:
                continue
            if stanowisko in (p.doswiadczenie or []):
                przypisani.append(i)
                if len(przypisani) >= obsada:
                    break

        przypisane_idx.update(przypisani)
        wyniki[stanowisko] = [
            {
                'imie': pracownicy[i].imie,
                'nazwisko': pracownicy[i].nazwisko,
                'doswiadczenie': pracownicy[i].doswiadczenie or [],
            }
            for i in przypisani
        ]

    plan.dopasowanie = wyniki
    plan.dopasowane_at = timezone.now()
    plan.save(update_fields=['dopasowanie', 'dopasowane_at'])
    return wyniki


def _importuj_plan(request, zmiana, template):
    if request.method != 'POST':
        ostatnie = PlanZmiany.objects.filter(zmiana=zmiana).first()
        return render(request, template, {'ostatni_import': ostatnie})

    plik = request.FILES.get('plik')
    if not plik:
        messages.error(request, 'Nie wybrano pliku.')
        return render(request, template)

    if not plik.name.lower().endswith('.xlsx'):
        messages.error(request, 'Nieprawidłowy format pliku. Wymagany plik .xlsx.')
        return render(request, template)

    try:
        tekst = _excel_na_tekst(plik)
    except Exception as exc:
        messages.error(request, f'Błąd odczytu pliku Excel: {exc}')
        return render(request, template)

    try:
        dane = _wywolaj_openai(tekst, nazwa_pliku=plik.name,
                               system_prompt=SYSTEM_PROMPT_PLAN, max_tokens=2000)
    except APIError as exc:
        messages.error(request, f'Błąd API OpenAI: {exc}')
        return render(request, template)
    except json.JSONDecodeError as exc:
        messages.error(request, f'Nie można sparsować odpowiedzi AI jako JSON: {exc}')
        return render(request, template)
    except Exception as exc:
        messages.error(request, f'Błąd podczas importu: {exc}')
        return render(request, template)

    if not isinstance(dane, list):
        messages.error(request, 'Odpowiedź AI nie jest tablicą JSON.')
        return render(request, template)

    PlanZmiany.objects.create(
        nazwa_pliku=plik.name,
        zmiana=zmiana,
        importowany_przez=request.user,
        dane_raw=dane,
    )

    ZMIANA_DISPLAY = {'poranny': 'poranny', 'popobudniowy': 'popołudniowy', 'nocny': 'nocny'}
    stanowisk = len(dane)
    total_obsada = sum(int(w.get('obsada') or 0) for w in dane)
    messages.success(request,
        f'Zaimportowano plan {ZMIANA_DISPLAY.get(zmiana, zmiana)}: {stanowisk} stanowisk, łączna obsada {total_obsada} osób.')
    return redirect('pracownicy:plany_lista')

# ── Widoki ────────────────────────────────────────────────────────────────────

@login_required
def lista(request):
    pracownicy = Pracownik.objects.all().order_by('nazwisko', 'imie')
    return render(request, 'pracownicy/lista.html', {'pracownicy': pracownicy})


@login_required
def import_excel(request):
    if request.method != 'POST':
        return render(request, 'pracownicy/import.html')

    plik = request.FILES.get('plik')
    if not plik:
        messages.error(request, 'Nie wybrano pliku.')
        return render(request, 'pracownicy/import.html')

    nazwa = plik.name.lower()
    if nazwa.endswith('.xlsx'):
        try:
            tekst = _excel_na_tekst(plik)
        except Exception as exc:
            messages.error(request, f'Błąd odczytu pliku Excel: {exc}')
            return render(request, 'pracownicy/import.html')
    elif nazwa.endswith('.csv'):
        try:
            tekst = _csv_na_tekst(plik)
        except Exception as exc:
            messages.error(request, f'Błąd odczytu pliku CSV: {exc}')
            return render(request, 'pracownicy/import.html')
    else:
        messages.error(request, 'Nieprawidłowy format pliku. Wymagany plik .xlsx lub .csv.')
        return render(request, 'pracownicy/import.html')

    try:
        dane = _wywolaj_openai(tekst, nazwa_pliku=plik.name, max_tokens=8192)
    except APIError as exc:
        messages.error(request, f'Błąd API OpenAI: {exc}')
        return render(request, 'pracownicy/import.html')
    except json.JSONDecodeError as exc:
        messages.error(request, f'Nie można sparsować odpowiedzi AI jako JSON: {exc}')
        return render(request, 'pracownicy/import.html')
    except Exception as exc:
        messages.error(request, f'Błąd podczas importu: {exc}')
        return render(request, 'pracownicy/import.html')

    if not isinstance(dane, list):
        messages.error(request, 'Odpowiedź AI nie jest tablicą JSON.')
        return render(request, 'pracownicy/import.html')

    ai_wierszy = len(dane)
    nowi = []
    pominieto = 0
    for item in dane:
        imie = (item.get('imie') or '').strip()
        nazwisko = (item.get('nazwisko') or '').strip()
        if not imie or not nazwisko:
            pominieto += 1
            continue
        doswiadczenie = [str(s).strip() for s in (item.get('doswiadczenie') or []) if str(s).strip()]
        nowi.append(Pracownik(imie=imie, nazwisko=nazwisko, doswiadczenie=doswiadczenie))

    Pracownik.objects.all().delete()
    Pracownik.objects.bulk_create(nowi)

    msg = f'Zaimportowano {len(nowi)} pracowników (AI wykryło {ai_wierszy} wierszy).'
    if pominieto:
        msg += f' Pominięto {pominieto} wierszy z pustym imieniem lub nazwiskiem.'
    messages.success(request, msg)
    return redirect('pracownicy:lista')


@login_required
def import_plan_poranny(request):
    return _importuj_plan(request, 'poranny', 'pracownicy/import_plan_poranny.html')


@login_required
def import_plan_popobudniowy(request):
    return _importuj_plan(request, 'popobudniowy', 'pracownicy/import_plan_popobudniowy.html')


@login_required
def import_plan_nocny(request):
    return _importuj_plan(request, 'nocny', 'pracownicy/import_plan_nocny.html')


@login_required
def plany_lista(request):
    # Słownik (imie, nazwisko) → doswiadczenie z aktualnej bazy
    lookup = {
        (p.imie, p.nazwisko): p.doswiadczenie or []
        for p in Pracownik.objects.all()
    }

    plany_raw = PlanZmiany.objects.all()
    plany = []
    for plan in plany_raw:
        stanowiska_dane = []
        total_dopasowanych = 0
        for wpis in (plan.dane_raw or []):
            stanowisko = wpis.get('stanowisko', '')
            obsada = wpis.get('obsada', 0)
            raw_workers = (plan.dopasowanie or {}).get(stanowisko, [])
            workers = []
            for w in raw_workers:
                imie, nazwisko = w.get('imie', ''), w.get('nazwisko', '')
                if (imie, nazwisko) not in lookup:
                    continue  # pracownik usunięty z bazy — ignoruj nieaktualne dopasowanie
                # użyj doswiadczenie zapisanego w dopasowaniu; fallback do bazy
                dosw = w.get('doswiadczenie') or lookup.get((imie, nazwisko), [])
                workers.append({'imie': imie, 'nazwisko': nazwisko, 'doswiadczenie': dosw})
            total_dopasowanych += len(workers)
            stanowiska_dane.append({
                'stanowisko': stanowisko,
                'obsada': obsada,
                'workers': workers,
                'workers_json': json.dumps(workers, ensure_ascii=False),
            })
        plany.append({
            'plan': plan,
            'stanowiska': stanowiska_dane,
            'total_dopasowanych': total_dopasowanych,
        })
    return render(request, 'pracownicy/plany_lista.html', {'plany': plany})


@login_required
def dopasuj_plan(request, pk):
    if request.method != 'POST':
        return redirect('pracownicy:plany_lista')
    plan = get_object_or_404(PlanZmiany, pk=pk)
    wyniki = _wykonaj_dopasowanie(plan)
    total = sum(len(v) for v in wyniki.values())
    messages.success(request,
        f'Dopasowano {total} pracowników do stanowisk z planu „{plan}".')
    return redirect('pracownicy:plany_lista')


@login_required
def zmien_typ_planu(request, pk):
    if request.method != 'POST':
        return redirect('pracownicy:plany_lista')
    plan = get_object_or_404(PlanZmiany, pk=pk)
    cykl = {'poranny': 'popobudniowy', 'popobudniowy': 'nocny', 'nocny': 'poranny', 'dzienny': 'poranny'}
    plan.zmiana = cykl.get(plan.zmiana, 'poranny')
    plan.save(update_fields=['zmiana'])
    messages.success(request, f'Zmieniono typ planu na: {plan.get_zmiana_display()}.')
    return redirect('pracownicy:plany_lista')


@login_required
def usun_plan(request, pk):
    if request.method != 'POST':
        return redirect('pracownicy:plany_lista')
    plan = get_object_or_404(PlanZmiany, pk=pk)
    nazwa = str(plan)
    plan.delete()
    messages.success(request, f'Usunięto plan: {nazwa}.')
    return redirect('pracownicy:plany_lista')


_PDF_FONTS_REGISTERED = False

def _znajdz_font(kandydaci):
    return next((p for p in kandydaci if os.path.exists(p)), None)

def _rejestruj_fonty_pdf():
    global _PDF_FONTS_REGISTERED
    if _PDF_FONTS_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    if sys.platform == 'win32':
        d = 'C:/Windows/Fonts'
        normal = os.path.join(d, 'arial.ttf')
        bold   = os.path.join(d, 'arialbd.ttf')
        italic = os.path.join(d, 'ariali.ttf')
    else:
        # Linux (PythonAnywhere / Ubuntu) — szuka DejaVu, Liberation lub Arial
        normal = _znajdz_font([
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf',
        ])
        bold = _znajdz_font([
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf',
        ])
        italic = _znajdz_font([
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
            '/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Oblique.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf',
            '/usr/share/fonts/truetype/msttcorefonts/Arial_Italic.ttf',
        ])
        if not normal:
            raise FileNotFoundError(
                'Brak czcionki TrueType obsługującej polskie znaki. '
                'Na serwerze uruchom: apt install fonts-dejavu-core'
            )

    pdfmetrics.registerFont(TTFont('Pl',   normal))
    pdfmetrics.registerFont(TTFont('Pl-B', bold   or normal))
    pdfmetrics.registerFont(TTFont('Pl-I', italic or normal))
    registerFontFamily('Pl', normal='Pl', bold='Pl-B', italic='Pl-I')
    _PDF_FONTS_REGISTERED = True


@login_required
def eksport_planu_pdf(request, pk):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    _rejestruj_fonty_pdf()
    plan = get_object_or_404(PlanZmiany, pk=pk)

    ZMIANA = {'poranny': 'porannej', 'popobudniowy': 'popołudniowej', 'nocny': 'nocnej'}
    s_normal = ParagraphStyle('n', fontName='Pl',   fontSize=9)
    s_bold   = ParagraphStyle('b', fontName='Pl-B', fontSize=9)
    s_title  = ParagraphStyle('t', fontName='Pl-B', fontSize=13)
    s_meta   = ParagraphStyle('m', fontName='Pl',   fontSize=8,  textColor=colors.HexColor('#555555'))
    s_footer = ParagraphStyle('f', fontName='Pl',   fontSize=8,  textColor=colors.HexColor('#888888'))
    s_gray   = ParagraphStyle('g', fontName='Pl',   fontSize=9,  textColor=colors.HexColor('#aaaaaa'))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=18*mm,   bottomMargin=18*mm)
    story = []

    story.append(Paragraph(
        f"Plan zmiany {ZMIANA.get(plan.zmiana, plan.zmiana)} – {plan.data_importu.strftime('%d.%m.%Y')}",
        s_title))
    story.append(Spacer(1, 2*mm))

    meta = (f"Plik: {plan.nazwa_pliku}  |  Stanowisk: {len(plan.dane_raw or [])}  |  "
            f"Wymagana obsada: {plan.total_obsada}")
    if plan.dopasowane_at:
        meta += f"  |  Dopasowano: {plan.dopasowane_at.strftime('%d.%m.%Y %H:%M')}"
    story.append(Paragraph(meta, s_meta))
    story.append(Spacer(1, 5*mm))

    header = [Paragraph(t, ParagraphStyle('h', fontName='Pl-B', fontSize=9, textColor=colors.white))
              for t in ['Stanowisko', 'Obsada', 'Dopasowani pracownicy', 'Wynik']]
    rows = [header]

    for wpis in (plan.dane_raw or []):
        stanowisko = wpis.get('stanowisko', '')
        obsada     = int(wpis.get('obsada') or 0)
        osoby      = (plan.dopasowanie or {}).get(stanowisko, [])
        dopasowano = len(osoby)

        if osoby:
            prac_txt = ', '.join(f"{o.get('imie','')} {o.get('nazwisko','')}" for o in osoby)
            prac_par = Paragraph(prac_txt, s_normal)
        elif plan.dopasowane_at:
            prac_par = Paragraph('— brak —', s_gray)
        else:
            prac_par = Paragraph('nie dopasowano', s_gray)

        if plan.dopasowane_at:
            wynik_txt = f'{dopasowano}/{obsada}'
            wynik_col = '#1a7f37' if dopasowano == obsada else ('#cf222e' if dopasowano == 0 else '#9a6700')
            wynik_par = Paragraph(wynik_txt, ParagraphStyle('w', fontName='Pl-B', fontSize=9,
                                                             textColor=colors.HexColor(wynik_col)))
        else:
            wynik_par = Paragraph(f'—/{obsada}', s_gray)

        rows.append([
            Paragraph(stanowisko, s_bold),
            Paragraph(str(obsada), ParagraphStyle('c', fontName='Pl', fontSize=9, alignment=1)),
            prac_par,
            wynik_par,
        ])

    col_w = [44*mm, 18*mm, 98*mm, 18*mm]
    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1,  0), colors.HexColor('#1a1d23')),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#e0e0e0')),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ALIGN',         (1, 0), (1, -1), 'CENTER'),
        ('ALIGN',         (3, 0), (3, -1), 'CENTER'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph(
        f"Wygenerowano: {timezone.now().strftime('%d.%m.%Y %H:%M')} "
        f"przez {request.user.username}  |  System Magazynowy",
        s_footer))

    doc.build(story)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="plan_{pk}_{plan.zmiana}.pdf"'
    return response


@login_required
def dane_edycji_planu(request, pk):
    plan = get_object_or_404(PlanZmiany, pk=pk)
    wszyscy = list(
        Pracownik.objects.order_by('nazwisko', 'imie').values('imie', 'nazwisko', 'doswiadczenie')
    )
    return JsonResponse({
        'dane_raw': plan.dane_raw or [],
        'dopasowanie': plan.dopasowanie or {},
        'wszyscy_pracownicy': wszyscy,
    })


@login_required
def edytuj_dopasowanie_planu(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    plan = get_object_or_404(PlanZmiany, pk=pk)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    nowe = body.get('dopasowanie', {})
    if not isinstance(nowe, dict):
        return JsonResponse({'error': 'dopasowanie must be a dict'}, status=400)

    znane = {w.get('stanowisko') for w in (plan.dane_raw or [])}
    for s in nowe:
        if s not in znane:
            return JsonResponse({'error': f'Nieznane stanowisko: {s}'}, status=400)

    plan.dopasowanie = nowe
    plan.dopasowane_at = timezone.now()
    plan.save(update_fields=['dopasowanie', 'dopasowane_at'])
    total = sum(len(v) for v in nowe.values())
    return JsonResponse({'status': 'ok', 'total_dopasowanych': total})


@login_required
def usun_pracownika(request, pk):
    if request.method != 'POST':
        return redirect('pracownicy:lista')
    pracownik = Pracownik.objects.filter(pk=pk).first()
    if pracownik:
        nazwa = f'{pracownik.imie} {pracownik.nazwisko}'
        pracownik.delete()
        messages.success(request, f'Usunięto pracownika: {nazwa}.')
    return redirect('pracownicy:lista')


@login_required
def usun_wszystkich(request):
    if request.method != 'POST':
        return redirect('pracownicy:lista')
    liczba, _ = Pracownik.objects.all().delete()
    PlanZmiany.objects.update(dopasowanie={}, dopasowane_at=None)
    messages.success(
        request,
        f'Usunięto wszystkich pracowników ({liczba}). '
        f'Wyczyszczono również dopasowania we wszystkich planach zmian.'
    )
    return redirect('pracownicy:lista')
