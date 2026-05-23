from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from datetime import timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from apps.rekruci.models import Rekrut
from apps.stanowiska.models import Stanowisko
from apps.przydzialy.models import Przydzia
from apps.scoring.engine import ScoringEngine

try:
    from weasyprint import HTML
    WEASYPRINT_OK = True
except Exception:
    WEASYPRINT_OK = False


@login_required
def karta_pdf(request, pk):
    rekrut = get_object_or_404(Rekrut, pk=pk)
    historia = rekrut.przydzia_set.select_related('stanowisko', 'autor').order_by('-data_przydzialu')[:5]
    aktualny = rekrut.przydzia_set.filter(aktywny=True).select_related('stanowisko').first()

    ostrzezenia = []
    try:
        if rekrut.orzeczenie.dni_do_wygasniecia <= 30:
            ostrzezenia.append(f'Orzeczenie lekarskie wygasa {rekrut.orzeczenie.data_waznosci:%d.%m.%Y}')
    except Exception:
        ostrzezenia.append('Brak orzeczenia lekarskiego')

    html_str = render_to_string('raporty/karta_rekruta_pdf.html', {
        'rekrut': rekrut,
        'historia': historia,
        'aktualny': aktualny,
        'ostrzezenia': ostrzezenia,
        'data_wydruku': timezone.now(),
    }, request=request)

    if WEASYPRINT_OK:
        pdf = HTML(string=html_str, base_url=request.build_absolute_uri('/')).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="karta_{rekrut.pk}.pdf"'
        return response
    else:
        return HttpResponse(html_str)


@login_required
def obsada_excel(request):
    wb = openpyxl.Workbook()

    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(fill_type='solid', fgColor='1F5C99')

    ws1 = wb.active
    ws1.title = 'Obsada stanowisk'
    headers1 = ['Stanowisko', 'Max pracowników', 'Aktualnie', 'Wolne miejsca', '% zapełnienia', 'Lista pracowników']
    for col, h in enumerate(headers1, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    stanowiska = Stanowisko.objects.filter(aktywne=True)
    for row, s in enumerate(stanowiska, 2):
        aktywne_przydzialy = Przydzia.objects.filter(stanowisko=s, aktywny=True).select_related('rekrut')
        aktualnie = aktywne_przydzialy.count()
        wolne = s.max_pracownikow - aktualnie
        proc = round(aktualnie / s.max_pracownikow * 100) if s.max_pracownikow else 0
        pracownicy = ', '.join(str(p.rekrut) for p in aktywne_przydzialy)
        ws1.append([s.nazwa, s.max_pracownikow, aktualnie, wolne, f'{proc}%', pracownicy])

    for col in range(1, 7):
        ws1.column_dimensions[get_column_letter(col)].auto_size = True
        ws1.column_dimensions[get_column_letter(col)].width = max(15, ws1.column_dimensions[get_column_letter(col)].width or 15)

    ws2 = wb.create_sheet('Bez przydziału')
    headers2 = ['Nazwisko', 'Imię', 'Wiek', 'Rekomendowane stanowisko', 'Score AI']
    for col, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    engine = ScoringEngine()
    rekruci = Rekrut.objects.filter(aktywny=True)
    row = 2
    for r in rekruci:
        if not r.przydzia_set.filter(aktywny=True).exists():
            wyniki = engine.score(r)
            top = next((w for w in wyniki if not w['blokady']), None)
            ws2.append([
                r.nazwisko, r.imie, r.wiek,
                top['stanowisko'].nazwa if top else 'Brak',
                top['score'] if top else 0,
            ])
            row += 1

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="obsada_{timezone.now():%Y%m%d}.xlsx"'
    wb.save(response)
    return response


@login_required
def ostrzezenia(request):
    today = timezone.now().date()
    deadline = today + timedelta(days=30)
    rekruci_ostrzezenia = Rekrut.objects.filter(
        aktywny=True,
        orzeczenie__data_waznosci__lte=deadline,
        orzeczenie__data_waznosci__gte=today,
    ).select_related('orzeczenie').order_by('orzeczenie__data_waznosci')
    return render(request, 'raporty/ostrzezenia.html', {
        'rekruci': rekruci_ostrzezenia,
        'today': today,
    })
