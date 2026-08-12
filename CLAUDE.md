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

# Run tests (Django TestCase, not pytest — no pytest.ini/conftest.py in this repo)
python manage.py test apps.pracownicy
python manage.py test

# One-off script (always add sys.path + django.setup first)
python -c "import sys,os; sys.path.insert(0,'c:/...path.../magazyn'); os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup(); ..."
```

**Two venvs exist for this project**: `magazyn\.venv` and a shared `myvenv` one level up (`My_Django_Projects\myvenv`). Confirm which one the dev server/IDE actually uses before installing a new dependency into only one of them — `pip install` silently succeeding in the wrong venv is a real failure mode here (hit in practice: `networkx` installed only into `.venv`, dev server ran under `myvenv` and crashed with `ModuleNotFoundError` on startup).

Test suite exists for `apps/pracownicy` (`tests.py`, ~20 tests covering the assignment engine). Verify changes by loading the page in the browser at `http://127.0.0.1:8000/`.

## Architecture

Django 5.2, SQLite, Bootstrap 5.3, no Celery, no AI (OpenAI removed in v2.0).

**Active modules:**

| App | Responsibility |
|---|---|
| `apps/pracownicy` | Core: workers, plans, assignment, import, macierz procesowa |
| `apps/konta` | Auth + roles (`admin`/`hr`/`kierownik`) |
| `apps/stanowiska` | Warehouse positions (CRUD, wired at `/stanowiska/`, `dodaj`/`edytuj`/`usun` gated `@wymaga_roli('admin')`) |
| `apps/notatki` | Shared notes panel (any logged-in user can delete any note — appears intentional, not an authz gap: the UI shows a delete button on every note to every user uniformly) |
| `apps/przydzialy` | Dashboard stub — obsada always shows 0, old `PlanZmiany`-based system disabled |

**Removed 2026-08-03** (dead code cleanup): `apps/rekruci` (Rekrut/AnkietaFizyczna/OrzeczenieLekarski — recruitment models, zero rows in DB, URLs never wired), `apps/scoring` (ScoringEngine, existed only to score `Rekrut` candidates), `apps/raporty` (its only view, `obsada_excel`, imported the models above and — since nothing populated them — always produced an effectively empty report). `Przydzia`/`AuditLog` (in `apps/przydzialy`) were deleted too since both existed only to record that dead Rekrut→Stanowisko assignment flow. `django-encrypted-model-fields`/`cryptography`/`FIELD_ENCRYPTION_KEY` also removed — they existed solely for `Rekrut`'s encrypted fields. See `apps/przydzialy/migrations/` history (rebuilt from scratch after this removal) if you need to trace it.

## Core data flow

```
Import Excel → PlanDzienny + ZapotrzebowanieGodzinowe
Import Excel → Pracownik + KompetencjaPracownika + AbsencjaPracownika
Import Excel → PracownikAPT + OcenaAPT

POST /plany/<pk>/przydziel/ → _wykonaj_przydzial() → PrzydzialDzienny.dane (JSON)
GET  /plany/<pk>/wyniki/    → wyniki_przydzialu() → renders wyniki_przydzialu.html
```

## Assignment algorithm — NetworkX min-cost flow (rewritten 2026-08-03)

`_wykonaj_przydzial` (views.py) is now a thin orchestrator around the real engine in
**`apps/pracownicy/przydzial_flow.py`**. `capacity = ceil(max hourly demand)` for each
(activity, shift), unchanged from before.

The old greedy phase-based algorithm (tier1/tier2/force-assign) is gone. It's replaced by
a strict **lexicographic** priority hierarchy — P1 dominates P2 completely, P2 dominates P3
completely — solved as one min-cost-flow problem per shift bucket instead of hand-rolled
sorting passes:

- **P1 — shift (A/B/C/D), hard constraint.** `pasuje_zmiana(pracownik, litera)` decides
  whether a worker→activity edge exists **at all** in the flow graph for that bucket. No
  edge, no possible assignment — modeled as absence, never as a high cost, so there's no
  way for a wrong-shift worker to slip through even as a last resort.
- **P2 — department match, soft but dominant.** `koszt_dopasowania()` fuzzy-matches
  `Pracownik.dzial` against `Aktywnosc.dzial` (`dzialy_fuzzy_match()`, difflib
  `SequenceMatcher`, accept ≥0.85, log-as-review-warning in [0.70, 0.85)) OR the existing
  departament-code keyword check (`_dept_matches_akt`, kept in views.py). Mismatch adds
  `PRZYDZIAL_PENALTY_DZIAL` (default 10 000) to the edge cost — large enough that no
  competency score (P3, capped at `PRZYDZIAL_KOSZT_MAX_KOMPETENCJI`, default 10) can ever
  outweigh it.
- **P3 — competency score.** Only breaks ties among workers who already passed P1 and share
  the same P2 status. Missing competency data doesn't raise — it's costed as the worst score
  plus a small `PRZYDZIAL_BRAK_KOMPETENCJI_PENALTY` (default 1), still far below the P2
  penalty.

`rozwiaz_zmiane()` builds one graph per bucket (source → eligible workers, capacity 1 each →
activities, capacity = `wymagana` → sink) and solves it with `networkx.max_flow_min_cost`,
which maximizes the *number* of assignments first and only then minimizes cost among
maximum-flow solutions — this is what lets a department-mismatched priority worker still get
placed (paying the P2 penalty) when no in-department candidate exists for that slot, without
a separate "force-assign" pass.

**Etat always before APT, by design (not a model limitation):** each shift bucket is solved
as *two* sequential flow problems — etat workers first, then APT against whatever residual
capacity remains (`rozwiaz_zmiane` called again with `residual = wymagana - already_filled`).
A well-matched APT worker can never displace a weaker etat worker. This was an explicit
choice, confirmed with the user, over unifying etat+APT into one competing pool.

**Audit fields** on every real assignment dict (new): `dzial_ok` (bool), `fuzzy_score`
(float), `kompetencja_uzyta` (float actually used for costing) — lets a future report
distinguish "ideal match" (shift+dept+high competency) from "emergency fill" (shift OK,
dept mismatched, used only because nothing better was available). Not yet surfaced in
`wyniki_przydzialu.html` — the template only reads named attributes, so these are additive
and safe, just unused by the UI today.

**Fillers:** unmatched workers still go to `__fillers__` key → rendered as "(bez przypisanej
aktywności)" — this part is unchanged. `_pasuje_do_aktywnosci` still exists in views.py but is
now used *only* to classify filler reason (`capacity` vs `no_match`), not to decide
assignments.

**Deliberate exception to P1:** workers with both `zmiana` and `zmiana_grupa` empty ("bez
zmiany") have no shift to be hard-filtered against — they fill residual gaps across shifts
1–3 (never shift D) in a separate P1-exempt flow pass, after the main per-shift solves. Same
for any APT worker left over after their own shift's solve. **This is not a bug**: a
compliance check that flags every `pasuje_zmiana() == False` assignment as a violation will
produce false positives for exactly this cohort — see `PrzydzialShiftComplianceTestCase` in
`tests.py` for the correct check (only workers with a *declared* shift preference count).

See `apps/pracownicy/przydzial_flow.py` docstrings and `apps/pracownicy/tests.py` for the
full cost model and test coverage.

### `worker_group_score[(worker_pk, plan_akt_pk)]`

Built by fuzzy-matching each plan activity to process groups, collecting all `czynnosci` from those groups, fetching `KompetencjaPracownika` rows for those activity PKs, and averaging per (worker, plan_activity). This means "Batch Mezz > szt > (Sort/PTS/PTL)" correctly uses competency scores from groups #9 and #38 even though the name doesn't exactly match any czynnosc.

### Shift assignment

`KonfiguracjaZmian` (singleton pk=1) maps shift number → letter (A/B/C/D). `pasuje_zmiana(pracownik, litera)` (in `przydzial_flow.py`) decides membership: exact match on `zmiana`, else prefix match on `zmiana_grupa` (e.g. `"A-1"` matches letter `"A"`). Workers with neither field set ("bez zmiany") are exempt from this check and fill residual gaps in shifts 1–3 only, in a separate pass after the main per-shift solves — see the Assignment algorithm section above.

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
- `mkdir -p` does not exist; use `python -c "import os; os.makedirs(..., exist_ok=True)"`.
- Venv: `.venv\Scripts\Activate.ps1` (PowerShell) or `.venv\Scripts\activate.bat` (cmd).

## Key model gotchas

- **`Pracownik` import is destructive**: every import calls `Pracownik.objects.all().delete()` then `bulk_create`. Always warn before importing workers.
- **`PrzydzialDzienny.dane`** keys: outer key = zmiana string — `"1"`/`"2"`/`"3"` (real shifts), `"4"` (shift D/PRASA-KDR, only present if any D-shift worker exists), `"0"` (leftover "bez zmiany" workers with no match at all, fillers-only). Inner keys = `str(akt_pk)` or `"__fillers__"`. An optional top-level `"__ostrzezenia_dzialow__"` key (list of strings) holds P2 fuzzy-match review warnings (ratio in [0.70, 0.85)) when any occurred.
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
