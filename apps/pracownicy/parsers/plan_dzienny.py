"""
Parser dla Plan_dzienny_NEW.xlsx.

Struktura pliku:
- Jeden arkusz "PLAN NEW"
- Sekcje działów wykrywane przez kolumna B == 'Bufor'
- Każdy wiersz aktywności zawiera 24 punkty godzinowe (3 zmiany × 8 godzin)

Indeksy kolumn (0-based):
  Zmiana I:   kolumny 11–18 (L–S),   godziny 6, 7, 8, 9, 10, 11, 12, 13
  Zmiana II:  kolumny 22–29 (W–AD),  godziny 14, 15, 16, 17, 18, 19, 20, 21
  Zmiana III: kolumny 33–40 (AH–AO), godziny 22, 23, 0, 1, 2, 3, 4, 5
"""
from dataclasses import dataclass, field
from typing import Optional
import openpyxl

ZMIANA_GODZINY = {
    1: [6, 7, 8, 9, 10, 11, 12, 13],
    2: [14, 15, 16, 17, 18, 19, 20, 21],
    3: [22, 23, 0, 1, 2, 3, 4, 5],
}

COL_WOLUMEN_I = 9    # J
COL_HOURS_I = 11     # L
COL_WOLUMEN_II = 20  # U
COL_HOURS_II = 22    # W
COL_WOLUMEN_III = 31 # AF
COL_HOURS_III = 33   # AH


@dataclass
class WierszPlanu:
    dzial: str
    aktywnosc: str
    wolumen_I: float
    wolumen_II: float
    wolumen_III: float
    godziny: dict  # {zmiana_int: {godzina_int: liczba_osob_float}}


def _to_float(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s or s.startswith('#'):
            return 0.0
        try:
            return float(s.replace(',', '.'))
        except ValueError:
            return 0.0
    return 0.0


def _is_error(val) -> bool:
    return isinstance(val, str) and val.strip().startswith('#')


def parsuj_plan_dzienny(plik) -> tuple[list[WierszPlanu], list[str]]:
    """
    Zwraca (wiersze, ostrzezenia).
    Każdy WierszPlanu zawiera 24 rekordy godzinowe w polu `godziny`.
    """
    wb = openpyxl.load_workbook(plik, data_only=True)

    ws = wb['PLAN NEW'] if 'PLAN NEW' in wb.sheetnames else wb.active

    wiersze: list[WierszPlanu] = []
    ostrzezenia: list[str] = []
    aktualny_dzial: Optional[str] = None

    for row in ws.iter_rows(values_only=True):
        if not row or all(c is None for c in row):
            continue

        col_a = row[0] if len(row) > 0 else None
        col_b = row[1] if len(row) > 1 else None

        # Wiersz nagłówka sekcji: kolumna B == 'Bufor'
        if isinstance(col_b, str) and col_b.strip() == 'Bufor':
            if col_a is not None:
                aktualny_dzial = str(col_a).strip()
            continue

        if aktualny_dzial is None or not col_a:
            continue

        aktywnosc = str(col_a).strip()
        if not aktywnosc or aktywnosc == aktualny_dzial:
            continue

        # Ostrzeżenia o błędach formuł
        for col_i in (COL_WOLUMEN_I, COL_WOLUMEN_II, COL_WOLUMEN_III):
            if col_i < len(row) and _is_error(row[col_i]):
                ostrzezenia.append(
                    f'Błąd formuły {row[col_i]} — wiersz „{aktywnosc}" '
                    f'(dział {aktualny_dzial}), traktowany jako 0'
                )

        wolumen_I = _to_float(row[COL_WOLUMEN_I] if COL_WOLUMEN_I < len(row) else None)
        wolumen_II = _to_float(row[COL_WOLUMEN_II] if COL_WOLUMEN_II < len(row) else None)
        wolumen_III = _to_float(row[COL_WOLUMEN_III] if COL_WOLUMEN_III < len(row) else None)

        godziny = {}
        for zmiana, start_col, hours in (
            (1, COL_HOURS_I, ZMIANA_GODZINY[1]),
            (2, COL_HOURS_II, ZMIANA_GODZINY[2]),
            (3, COL_HOURS_III, ZMIANA_GODZINY[3]),
        ):
            g = {}
            for i, h in enumerate(hours):
                ci = start_col + i
                g[h] = _to_float(row[ci] if ci < len(row) else None)
            godziny[zmiana] = g

        wiersze.append(WierszPlanu(
            dzial=aktualny_dzial,
            aktywnosc=aktywnosc,
            wolumen_I=wolumen_I,
            wolumen_II=wolumen_II,
            wolumen_III=wolumen_III,
            godziny=godziny,
        ))

    return wiersze, ostrzezenia
