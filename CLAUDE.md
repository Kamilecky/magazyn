# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate venv (PowerShell)
.venv\Scripts\Activate.ps1

# Run dev server
python manage.py runserver

# Apply migrations
python manage.py migrate

# Create new migration after model changes
python manage.py makemigrations

# Django shell
python manage.py shell

# One-off script (always add sys.path + django.setup first)
python -c "import sys,os; sys.path.insert(0,'c:/...path.../magazyn'); os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup(); ..."
```

No test suite exists. Verify changes by loading the page in the browser at `http://127.0.0.1:8000/`.

## Architecture

Django 5.2, SQLite, Bootstrap 5.3, no Celery, no AI (OpenAI removed in v2.0).

**Active modules:**

| App | Responsibility |
|---|---|
| `apps/pracownicy` | Core: workers, plans, assignment, import, macierz procesowa |
| `apps/konta` | Auth + roles (`admin`/`hr`/`kierownik`) |
| `apps/stanowiska` | Warehouse positions (CRUD) |
| `apps/notatki` | Notes |
| `apps/przydzialy` | Legacy dashboard (stub) |
| `apps/raporty` | Excel export |

`apps/rekruci` and `apps/scoring` are legacy — preserved in DB, URLs not wired.

## Core data flow

```
Import Excel → PlanDzienny + ZapotrzebowanieGodzinowe
Import Excel → Pracownik + KompetencjaPracownika + AbsencjaPracownika
Import Excel → PracownikAPT + OcenaAPT

POST /plany/<pk>/przydziel/ → _wykonaj_przydzial() → PrzydzialDzienny.dane (JSON)
GET  /plany/<pk>/wyniki/    → wyniki_przydzialu() → renders wyniki_przydzialu.html
```

## Assignment algorithm — `_wykonaj_przydzial` (views.py)

`capacity = ceil(max hourly demand)` for each (activity, shift).

**Phase 1 — pre-reservation by macierz procesowa:**
For each worker, find the plan activity where their `worker_group_score` is highest. Sort workers by best score descending and assign them greedily. This ensures top-ranked workers from the process matrix land in the correct activity.

**Phase 2 — fill remaining capacity:**
Candidates must pass `_pasuje_do_aktywnosci` OR have `komp_map` entry OR have `worker_group_score > 0`. Sorted by group score desc → priority dept first → surname.

**Phase 3 — APT workers** fill whatever capacity remains, sorted by `comp_apt[(apt_pk, akt_pk)]` desc.

**Force-assign:** priority-dept workers left unassigned after phases 1–2 are placed in their first matching activity.

**Fillers:** unmatched workers go to `__fillers__` key → rendered as "(bez przypisanej aktywności)".

### `worker_group_score[(worker_pk, plan_akt_pk)]`

Built by fuzzy-matching each plan activity to process groups, collecting all `czynnosci` from those groups, fetching `KompetencjaPracownika` rows for those activity PKs, and averaging per (worker, plan_activity). This means "Batch Mezz > szt > (Sort/PTS/PTL)" correctly uses competency scores from groups #9 and #38 even though the name doesn't exactly match any czynnosc.

### Shift assignment

`KonfiguracjaZmian` (singleton pk=1) maps shift number → letter (A/B/C). Worker goes to shift where `zmiana_grupa` starts with the corresponding letter. Workers with no `zmiana_grupa` assigned to the first shift where they haven't appeared globally.

## Fuzzy-matching system (module-level in views.py)

`_find_all_groups(akt_nazwa)` resolves a plan activity name to `GRUPY_PROCESOWE` groups. Fallback chain:
1. Exact czynnosc match (`_akt_to_group_exact`)
2. Group name substring (min 3 chars) or word-set subset (min 2 words)
3. Czynnosc substring (min 4 chars) or word-set subset
4. `_MANUAL_MAP` — hardcoded for known typos and unmatchable names

`_nrm(s)` — lowercase, collapse whitespace, remove space before `)` or `]`.
`_words(s)` — `_nrm` + strip punctuation + keep only words ≥ 3 chars.

All five symbols (`_nrm`, `_words`, `_akt_to_group_exact`, `_MANUAL_MAP`, `_GP_BY_NR`, `_find_all_groups`) are **module-level** so `_wykonaj_przydzial` can call them without circular dependency.

### `grupy_procesowe.py`

57 process groups (`GRUPY_PROCESOWE: list[dict]`), each `{nr, nazwa, czynnosci: [str]}`. 158 czynnosci total. Currently 75/78 plan activities match; 3 unmatched are aggregate metrics (`SKU do przyjęcia`, `Struktura`, `Suma do Przyjęcia`).

## `wyniki_przydzialu.html` — modal system

Three Bootstrap 5 modal triggers all share `#aktModal`:

| Trigger class | Data attribute | Shows |
|---|---|---|
| `.akt-modal-trigger` | `data-akt-nazwa` | Process groups + czynnosci (green=in DB) + scored workers |
| `.dzial-modal-trigger` | `data-dzial-nazwa` | All process groups for that dept, aggregated across its activities |
| `.prac-modal-trigger` | `data-prac-pk` | Worker's top 4 competencies + process group rankings |

JSON blobs from context: `MODAL_DATA`, `WORKER_DATA`, `DZIAL_DATA` (rendered via `|safe` in `{% block extra_js %}`).

**APT workers** display with `background-color:#fefce8` (inline, not Bootstrap class — Bootstrap's `bg-warning-subtle` renders dark in dark mode).

## Windows-specific

- **File paths in tools**: always use forward slashes (`C:/path/file`) — backslash paths silently fail.
- PDF generation reads `C:/Windows/Fonts/arial.ttf`.
- `mkdir -p` does not exist; use `python -c "import os; os.makedirs(..., exist_ok=True)"`.
- Venv: `.venv\Scripts\Activate.ps1` (PowerShell) or `.venv\Scripts\activate.bat` (cmd).

## Key model gotchas

- **`Pracownik` import is destructive**: every import calls `Pracownik.objects.all().delete()` then `bulk_create`. Always warn before importing workers.
- **`PrzydzialDzienny.dane`** keys: outer key = zmiana string (`"1"`, `"2"`, `"3"`); inner keys = `str(akt_pk)` or `"__fillers__"`.
- **`KonfiguracjaZmian.pobierz()`** — singleton via `get_or_create(pk=1)`. Don't create additional instances.
- **`Aktywnosc` unique_together `('nazwa', 'dzial')`** — same activity name can appear in multiple działy.
- `KompetencjaPracownika` only stores rows where `wynik > 0`. Absence of a row means score=0, not missing data.

## Import file formats (quick reference)

| File | Parser | Key detail |
|---|---|---|
| `Plan_dzienny_NEW.xlsx` | `parsers/plan_dzienny.py` | Col B == `'Bufor'` → dział header row |
| `KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx` | `parsers/kompetencje.py` | Rows 3–5 merged header; col 11 = `zmiana_grupa`; skip cols with `'prasa'` in dział name |
| `Struktura___Grafik___Absencje_NEW.xlsx` | `parsers/struktura.py` | Sheets `Struktura IB/OB/FF/PR/ZW`; row 6 = header; date cols → AbsencjaPracownika |
| `PracownicyAPT*.xlsx` | `parsers/pracownicy_apt.py` | Sheet `PracownicyAPT01`; cols 2–18 (mapped via SCORE_COLS) → OcenaAPT |

Two-file worker import: structure data **overwrites** kompetencje data for the same `(nazwisko, imie)` key.

## Template inheritance

All templates extend `templates/base.html`. Use `{% block content %}` for page body and `{% block extra_js %}` for page-specific scripts. Content placed between `{% endblock %}` tags outside any block is silently discarded.
