"""
Parser dla Struktura___Grafik___Absencje_NEW.xlsx.

Struktura:
- Arkusze: "Struktura IB", "Struktura OB", "Struktura FF", "Struktura PR", "Struktura ZW"
- Arkusz "Listy Rozwijane": źródło prawdy dla typów absencji (kolumna B)
- Wiersze 1–5: statystyki zbiorcze (pomijane)
- Wiersz 6: nagłówki kolumn
- Wiersz 7+: dane pracowników; kolumny z datami = obecność/absencja
"""
from datetime import date, datetime
import openpyxl

ARKUSZE_DZIALY = {
    'Struktura IB': 'Inbound',
    'Struktura OB': 'Outbound',
    'Struktura FF': 'Fulfilment',
    'Struktura PR': 'Prasa',
    'Struktura ZW': 'Zwroty',
}

PRACOWNIK_NAGLOWKI = {
    'Nazwisko': 'nazwisko',
    'Imię': 'imie',
    'Nr ewidencyjny': 'nr_ewidencyjny',
    'Data zatrudnienia': 'data_zatrudnienia',
    'Stanowisko': 'stanowisko',
    'Strefa': 'strefa',
    'Dział': 'dzial',
    'Zmiana': 'zmiana',
    'Zmiana grupa': 'zmiana_grupa',
    'Przełożony': 'przelozony',
}

DOMYSLNE_TYPY_ABSENCJI = {'Nieobecny'}


def _safe_str(val) -> str:
    return str(val).strip() if val is not None else ''


def _parse_date(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.isoformat()[:10]
    s = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _try_parse_date(val) -> str | None:
    if isinstance(val, (date, datetime)):
        return val.isoformat()[:10]
    if isinstance(val, str):
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(val.strip(), fmt).date().isoformat()
            except ValueError:
                pass
    return None


def parsuj_strukture(plik) -> tuple[list[dict], list[dict], list[str]]:
    """
    Zwraca (pracownicy_list, absencje_list, ostrzezenia).
    """
    wb = openpyxl.load_workbook(plik, data_only=True)

    # Wczytaj typy absencji z arkusza pomocniczego
    typy_absencji = set(DOMYSLNE_TYPY_ABSENCJI)
    if 'Listy Rozwijane' in wb.sheetnames:
        ws_lr = wb['Listy Rozwijane']
        for row in ws_lr.iter_rows(values_only=True, min_row=2):
            val = row[1] if len(row) > 1 else None
            if val and isinstance(val, str) and val.strip():
                typy_absencji.add(val.strip())

    all_pracownicy: dict[tuple, dict] = {}
    all_absencje: list[dict] = []
    ostrzezenia: list[str] = []

    dostepne_arkusze = [n for n in wb.sheetnames if n in ARKUSZE_DZIALY]
    if not dostepne_arkusze:
        ostrzezenia.append(
            'Nie znaleziono żadnego arkusza struktury '
            '(oczekiwano: Struktura IB / OB / FF / PR / ZW).'
        )
        return [], [], ostrzezenia

    for sheet_name in dostepne_arkusze:
        ws = wb[sheet_name]
        p, a, o = _parsuj_arkusz(ws, sheet_name, typy_absencji)
        for key, data in p.items():
            all_pracownicy[key] = {**all_pracownicy.get(key, {}), **data}
        all_absencje.extend(a)
        ostrzezenia.extend(o)

    return list(all_pracownicy.values()), all_absencje, ostrzezenia


def _parsuj_arkusz(ws, sheet_name: str, typy_absencji: set) -> tuple[dict, list, list]:
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 7:
        return {}, [], [f'Arkusz {sheet_name}: zbyt mało wierszy']

    # Wiersz 6 (0-indexed: 5) = nagłówki kolumn
    header_row = rows[5]

    col_indices: dict[str, int] = {}
    date_cols: dict[int, str] = {}  # col_idx → data ISO

    for i, header in enumerate(header_row):
        if header is None:
            continue
        header_str = str(header).strip()
        if header_str in PRACOWNIK_NAGLOWKI:
            col_indices[PRACOWNIK_NAGLOWKI[header_str]] = i
        else:
            d = _try_parse_date(header)
            if d:
                date_cols[i] = d

    if 'nazwisko' not in col_indices or 'imie' not in col_indices:
        return {}, [], [f'Arkusz {sheet_name}: brak kolumn Nazwisko/Imię w nagłówku']

    nazwisko_i = col_indices['nazwisko']
    imie_i = col_indices['imie']

    pracownicy: dict[tuple, dict] = {}
    absencje: list[dict] = []

    for row in rows[6:]:
        if not row:
            continue
        nazwisko_raw = row[nazwisko_i] if nazwisko_i < len(row) else None
        imie_raw = row[imie_i] if imie_i < len(row) else None
        if not nazwisko_raw or not imie_raw:
            continue
        nazwisko = _safe_str(nazwisko_raw)
        imie = _safe_str(imie_raw)
        if not nazwisko or not imie:
            continue

        key = (nazwisko, imie)
        p_data: dict = {'nazwisko': nazwisko, 'imie': imie}
        for field, ci in col_indices.items():
            if ci < len(row) and row[ci] is not None:
                raw = row[ci]
                if field == 'data_zatrudnienia':
                    p_data[field] = _parse_date(raw)
                else:
                    p_data[field] = _safe_str(raw)
        pracownicy[key] = p_data

        for ci, data_iso in date_cols.items():
            if ci >= len(row):
                continue
            cell = row[ci]
            if cell is None:
                continue
            cell_str = _safe_str(cell)
            if cell_str in typy_absencji:
                absencje.append({
                    'pracownik_klucz': f'{nazwisko}|{imie}',
                    'data': data_iso,
                    'typ': cell_str,
                })

    return pracownicy, absencje, []
