# System Magazynowy — Dokumentacja projektu

## Spis treści

1. [Przegląd systemu](#1-przegląd-systemu)
2. [Stos technologiczny](#2-stos-technologiczny)
3. [Struktura projektu](#3-struktura-projektu)
4. [Baza danych — modele](#4-baza-danych--modele)
5. [Moduły i funkcje](#5-moduły-i-funkcje)
6. [Algorytm przydziału pracowników](#6-algorytm-przydziału-pracowników)
7. [Routing URL](#7-routing-url)
8. [Konfiguracja i zmienne środowiskowe](#8-konfiguracja-i-zmienne-środowiskowe)
9. [Uruchomienie projektu](#9-uruchomienie-projektu)
10. [Format plików do importu](#10-format-plików-do-importu)
11. [Znane ograniczenia](#11-znane-ograniczenia)

---

## 1. Przegląd systemu

System Magazynowy to aplikacja webowa zbudowana w Django 5.2, przeznaczona do zarządzania pracownikami magazynowymi — importu danych kadrowych, planów zapotrzebowania godzinowego, macierzy kompetencji oraz automatycznego przydziału pracowników do aktywności.

**Główny przepływ pracy:**

1. **Import planu dziennego** — wgraj plik `Plan_dzienny_NEW.xlsx`; parser odczytuje zapotrzebowanie godzinowe na 3 zmiany i zapisuje rekordy `ZapotrzebowanieGodzinowe`
2. **Import pracowników** — wgraj plik `KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx` i/lub `Struktura___Grafik___Absencje_NEW.xlsx`; dane scalane w profil pracownika wraz z `zmiana_grupa`
3. **Import pracowników APT** — skonfiguruj mapowanie kolumn 1–14 na działy, wgraj plik z ocenami
4. **Przydział pracowników** — kliknij „Przydziel" na planie; algorytm przydziela pracowników do aktywności według zmian, kompetencji i priorytetu departamentów
5. **Wyniki przydziału** — tabela z zakładkami zmian, tabelami godzinowymi (Plan/Fakt), listą pracowników z kolorowym badge'em grupy zmiany i wskaźnikiem nieobecności

Dostęp do wszystkich widoków wymaga zalogowania. Parser nie korzysta z AI — wszystkie kolumny rozpoznawane są deterministycznie.

---

## 2. Stos technologiczny

| Warstwa | Technologia |
|---|---|
| Backend | Django 5.2, Python 3.13 |
| Baza danych | SQLite (dev), PostgreSQL (prod) |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.11, Vanilla JS |
| Excel (odczyt) | openpyxl 3.1.5 |
| PDF | reportlab — czcionka Arial z `C:/Windows/Fonts` |
| Szyfrowanie pól | django-encrypted-model-fields 0.6.5 + cryptography |
| Zmienne środowiskowe | django-environ 0.11.2 |
| Serwowanie plików statycznych | WhiteNoise 6.8.2 |

> **Uwaga:** OpenAI API zostało usunięte w wersji 2.0 (2026-07-04). Import pracowników i planów nie wymaga klucza API ani połączenia z siecią.

---

## 3. Struktura projektu

```
magazyn/
├── apps/
│   ├── konta/              # Uwierzytelnianie i role użytkowników
│   ├── pracownicy/         # Główny moduł: pracownicy, import, plany, przydział
│   │   ├── parsers/        # Deterministyczne parsery Excel
│   │   │   ├── plan_dzienny.py       # Parser Plan_dzienny_NEW.xlsx
│   │   │   ├── kompetencje.py        # Parser KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx
│   │   │   ├── struktura.py          # Parser Struktura___Grafik___Absencje_NEW.xlsx
│   │   │   └── pracownicy_apt.py     # Parser PracownicyAPT*.xlsx
│   │   ├── templatetags/
│   │   │   └── pracownicy_extras.py  # Filtr get_item dla słowników w szablonach
│   │   ├── migrations/
│   │   ├── models.py
│   │   ├── views.py                  # Lista, plany, przydział, import
│   │   ├── urls.py                   # /pracownicy/ — namespace: pracownicy
│   │   └── urls_import.py            # /import/ — namespace: import_danych
│   ├── rekruci/            # Legacy (zachowany w bazie, URL niedostępny)
│   ├── stanowiska/         # Stanowiska magazynowe
│   ├── przydzialy/         # Dashboard obsady (legacy)
│   ├── scoring/            # Legacy: silnik scoringu AI
│   └── raporty/            # Eksport Excel
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── templates/
│   ├── base.html
│   ├── pracownicy/
│   │   ├── lista.html
│   │   ├── plany_lista.html
│   │   ├── wyniki_przydzialu.html    # Wyniki przydziału pracowników do planu
│   │   ├── import_plan_zmianowy.html
│   │   ├── import_pracownicy.html
│   │   ├── import_pracownicy_apt.html
│   │   └── plan_pdf.html
│   ├── stanowiska/
│   ├── przydzialy/
│   ├── raporty/
│   └── konta/
├── tmp/                    # Pliki tymczasowe podglądu importu (UUID.json)
├── .env
├── requirements.txt
├── manage.py
└── db.sqlite3
```

---

## 4. Baza danych — modele

### 4.1 `pracownicy.Aktywnosc`

| Pole | Typ | Opis |
|---|---|---|
| `nazwa` | CharField(200) | Nazwa aktywności |
| `dzial` | CharField(100) | Dział, do którego należy aktywność |

**Unikalność:** `unique_together = ('nazwa', 'dzial')`

---

### 4.2 `pracownicy.PlanDzienny`

| Pole | Typ | Opis |
|---|---|---|
| `nazwa_pliku` | CharField(255) | Oryginalna nazwa wgranego pliku |
| `data_planu` | DateField(null, blank) | Data, której dotyczy plan (opcjonalna) |
| `data_importu` | DateTimeField | Czas wgrania (auto_now_add) |
| `importowany_przez` | FK(User, SET_NULL, null) | Użytkownik, który wgrał plan |

> `data_planu` jest używana do sprawdzania absencji pracowników w dniu planu. Jeśli pusta, absencje nie są oznaczane.

---

### 4.3 `pracownicy.ZapotrzebowanieGodzinowe`

Jedno zapotrzebowanie = jedna godzina dla jednej aktywności w jednym planie.

| Pole | Typ | Opis |
|---|---|---|
| `plan` | FK(PlanDzienny, CASCADE) | Powiązany plan |
| `aktywnosc` | FK(Aktywnosc, CASCADE) | Aktywność |
| `zmiana` | IntegerField | `1` = rano (6–13), `2` = popołudnie (14–21), `3` = noc (22–23, 0–5) |
| `godzina` | IntegerField (0–23) | Godzina doby |
| `liczba_osob` | FloatField | Wymagana liczba pracowników |
| `wolumen` | FloatField (null) | Wolumen (opcjonalnie z pliku) |

**Unikalność:** `unique_together = ('plan', 'aktywnosc', 'zmiana', 'godzina')`

**Mapowanie zmian na kolumny Excel:**

| Zmiana | Kolumny (0-indexed) | Godziny |
|---|---|---|
| I (rano) | L–S (11–18) | 6, 7, 8, 9, 10, 11, 12, 13 |
| II (popołudnie) | W–AD (22–29) | 14, 15, 16, 17, 18, 19, 20, 21 |
| III (noc) | AH–AO (33–40) | 22, 23, 0, 1, 2, 3, 4, 5 |

---

### 4.4 `pracownicy.PrzydzialDzienny`

Wynik przydziału pracowników do planu. Jeden rekord na plan (OneToOne).

| Pole | Typ | Opis |
|---|---|---|
| `plan` | OneToOne(PlanDzienny, CASCADE) | Powiązany plan |
| `dane` | JSONField | Pełny wynik przydziału (struktura opisana w sekcji 6) |
| `data_przydzialu` | DateTimeField | Czas ostatniego przeliczenia (auto_now) |

---

### 4.5 `pracownicy.Pracownik`

| Pole | Typ | Opis |
|---|---|---|
| `nr_ewidencyjny` | CharField(50, null) | Numer ewidencyjny |
| `imie` | CharField(100) | Imię |
| `nazwisko` | CharField(100) | Nazwisko |
| `departament` | CharField(20, blank) | Kod departamentu: `IN`, `OB`, `FF`, `ZW`, `PR` (priorytetowe) |
| `stanowisko` | CharField(100, blank) | Stanowisko |
| `strefa` | CharField(50, blank) | Strefa magazynowa |
| `dzial` | CharField(100, blank) | Dział (z pliku struktury) |
| `zmiana` | CharField(5, blank) | Zmiana (np. `I`, `II`, `III`) |
| `zmiana_grupa` | CharField(10, blank) | Grupa zmiany (np. `A-1`, `B-2`, `C-3`) |
| `przelozony` | CharField(100, blank) | Przełożony |
| `komentarz` | TextField(blank) | Komentarz |
| `data_zatrudnienia` | DateField(null) | Data zatrudnienia |

**Import:** każdy import zastępuje wszystkich pracowników (`Pracownik.objects.all().delete()` + `bulk_create`).

**Źródło `zmiana_grupa`:** kolumna L (indeks 11) w pliku KOMPETENCJE, nadpisywana przez pole „Zmiana grupa" z pliku Struktury jeśli oba pliki importowane jednocześnie.

---

### 4.6 `pracownicy.KompetencjaPracownika`

| Pole | Typ | Opis |
|---|---|---|
| `pracownik` | FK(Pracownik, CASCADE) | Pracownik |
| `aktywnosc` | FK(Aktywnosc, CASCADE) | Aktywność |
| `wynik` | FloatField | Ocena (tylko rekordy z `wynik > 0` są zapisywane) |

**Unikalność:** `unique_together = ('pracownik', 'aktywnosc')`

---

### 4.7 `pracownicy.AbsencjaPracownika`

| Pole | Typ | Opis |
|---|---|---|
| `pracownik` | FK(Pracownik, CASCADE) | Pracownik |
| `data` | DateField | Data absencji |
| `typ` | CharField(50) | Typ absencji (z listy w arkuszu „Listy Rozwijane") |

**Unikalność:** `unique_together = ('pracownik', 'data')`

---

### 4.8 `pracownicy.PracownikAPT`

| Pole | Typ | Opis |
|---|---|---|
| `nazwisko` | CharField(100) | Nazwisko |
| `imie` | CharField(100) | Imię |
| `nazwa_agencji` | CharField(50) | Nazwa agencji |
| `plec` | CharField(10, blank) | Płeć |
| `grupa` | CharField(50, blank) | Grupa zmiany (analogicznie do `zmiana_grupa`) |

---

### 4.9 `pracownicy.KolumnaAPT`

| Pole | Typ | Opis |
|---|---|---|
| `numer_kolumny` | IntegerField (unique) | Numer kolumny APT (1–14) |
| `nazwa_dzialu` | CharField(100) | Przypisana nazwa działu |

---

### 4.10 `pracownicy.OcenaAPT`

| Pole | Typ | Opis |
|---|---|---|
| `pracownik_apt` | FK(PracownikAPT, CASCADE) | Pracownik APT |
| `numer_kolumny` | IntegerField | Numer kolumny (1–14) |
| `ocena` | FloatField (null) | Wartość oceny |

**Unikalność:** `unique_together = ('pracownik_apt', 'numer_kolumny')`

---

### 4.11 `stanowiska.Stanowisko`

| Pole | Typ | Opis |
|---|---|---|
| `nazwa` | CharField(200) | Nazwa stanowiska |
| `wymagana_sila_kg` | IntegerField | Wymagana siła fizyczna w kg |
| `zakres_dzwigania` | CharField | `0-5`, `6-10`, `11-15`, `16-20`, `>20` |
| `poziom_chodzenia` | IntegerField(1–5) | Intensywność chodzenia |
| `poziom_siedzenia` | IntegerField(1–5) | Intensywność siedzenia |
| `powtarzalnosc_czynnosci` | IntegerField(1–5) | Powtarzalność czynności |
| `praca_stojaca` | BooleanField | Praca na stojąco |
| `praca_przy_monitorze` | BooleanField | Praca przy ekranie |
| `wymaga_komputera` | BooleanField | Wymagany komputer |
| `praca_na_zewnatrz` | BooleanField | Praca na zewnątrz |
| `max_pracownikow` | IntegerField | Maksymalna liczba pracowników |
| `aktywne` | BooleanField | Czy stanowisko aktywne |

---

### 4.12 `konta.Profil`

| Pole | Typ | Opis |
|---|---|---|
| `user` | OneToOne(User) | Django User |
| `rola` | CharField | `admin`, `hr`, `kierownik` |

---

## 5. Moduły i funkcje

### 5.1 Moduł `pracownicy`

#### Lista pracowników (`/pracownicy/`)

Tabela pracowników z filtrami (szukaj, dział, nieobecni), sortowaniem A–Z / Z–A, paginacją (50 na stronę). Kolumny: inicjały, imię/nazwisko, dział, zmiana, zmiana/grupa, stanowisko, liczba kompetencji. Kliknięcie w liczbę kompetencji otwiera modal z listą aktywności (AJAX).

---

#### Lista APT (`/pracownicy/apt/`)

Tabela pracowników APT z filtrem po agencji i wyszukiwaniem. Kolumny: nazwisko, imię, agencja, płeć, grupa.

---

#### Plany dzienne (`/pracownicy/plany/`)

Kafelki planów. Każdy kafelek zawiera: nazwę pliku, datę importu, liczbę aktywności, liczbę rekordów godzinowych, status przydziału (jeśli istnieje `PrzydzialDzienny`), przyciski „Przydziel" i „Wyniki" (gdy przydział istnieje).

---

#### Przydział pracowników (`/pracownicy/plany/<pk>/przydziel/` — POST)

Widok wywołuje `_wykonaj_przydzial(plan)` i zapisuje wynik w `PrzydzialDzienny`. Szczegóły algorytmu w sekcji 6.

---

#### Wyniki przydziału (`/pracownicy/plany/<pk>/wyniki/`)

Strona wynikowa przydziału. Składa się z:

- **Podsumowanie** — trzy kafelki (Zmiana I/II/III) z liczbą przypisanych i fillersów
- **Zakładki** — osobna zakładka na każdą zmianę z liczbą pracowników w badge
- **Na każdą aktywność:**
  - Nagłówek: nazwa, ikona ostrzeżenia przy niedoborze, badge `przydzielono / wymagana`
  - Tabela godzinowa „Plan / Fakt": kolumny = godziny zmiany; „Plan" = wymagana liczba (komórki czerwone przy niedoborze), „Fakt" = faktyczna obsada
  - Lista pracowników: badge z grupą zmiany (`A-1` zielony, `B-2` niebieski, `C-3` czerwony), badge APT (żółty), tooltip z pełnym imieniem, grupą i literą `N` dla nieobecnych
- **„(bez przypisanej aktywności)"** — filler: pracownicy, którym nie przydzielono żadnej aktywności

---

#### Import planu zmianowego (`/import/plan-zmianowy/`)

Dwuetapowy (upload → podgląd → zatwierdź). Zapisuje `PlanDzienny` + rekordy `ZapotrzebowanieGodzinowe` przez `bulk_create`. Pliki tymczasowe w `tmp/<UUID>.json`.

---

#### Import pracowników (`/import/pracownicy/`)

Dwuetapowy import z opcjonalnymi dwoma plikami.

**Scalanie danych:** `pracownicy_dict[key] = {**kompetencje_dane, **struktura_dane}` — struktura nadpisuje kompetencje dla tych samych kluczy `(nazwisko, imie)`. `zmiana_grupa` czytana z obu plików (kolumna L w KOMPETENCJE, kolumna „Zmiana grupa" w Strukturze).

Po zatwierdzeniu: `Pracownik.objects.all().delete()` + `bulk_create` pracowników, kompetencji, absencji.

---

#### Import pracowników APT (`/import/pracownicy-apt/`)

Sekcja mapowania kolumn (`action='save_mapping'`) + dwuetapowy import. Po zatwierdzeniu: `PracownikAPT.objects.all().delete()` + `bulk_create`.

---

### 5.2 Parsery Excel

#### `plan_dzienny.py`
- `WierszPlanu` dataclass: `aktywnosc`, `dzial`, `wolumen`, `zmianaI[8]`, `zmianaII[8]`, `zmianaIII[8]`
- Kolumna B == `'Bufor'` → wiersz nagłówka działu
- `_to_float()`: `None` → 0, `#DIV/0!` → 0 + ostrzeżenie

#### `kompetencje.py`
- Kolumny 0–13: dane pracownika (w tym indeks 11 = `zmiana_grupa`)
- `_forward_fill()` dla scalonych komórek nagłówkowych
- Kolumny 14+: aktywności; tylko `wynik > 0` zapisywany
- Pomija kolumny z `'prasa'` w nazwie działu

#### `struktura.py`
- Arkusze: `Struktura IB/OB/FF/PR/ZW`
- Wiersz 6 (1-indexed) = nagłówki, wiersz 7+ = dane
- Daty w nagłówkach → rekordy absencji; typy z arkusza `Listy Rozwijane` col B

#### `pracownicy_apt.py`
- Arkusz `PracownicyAPT01`
- `SCORE_COLS = {2:1, 3:2, 4:3, 5:4, 6:5, 8:6, 9:7, 10:8, 13:9, 14:10, 15:11, 16:12, 17:13, 18:14}`

---

### 5.3 Pozostałe moduły

**`stanowiska`** — CRUD stanowisk magazynowych z parametrami fizycznymi. Pasy obsady stub (0).

**`przydzialy`** — legacy dashboard i historia przydziałów z modelu `Przydzia`.

**`raporty`** — raport obsady w formacie Excel (`/raporty/obsada/excel/`).

**`konta`** — logowanie; `admin` → `/admin/`, inne role → `/pracownicy/`.

---

### 5.4 Nawigacja — Sidebar

| Sekcja | Linki |
|---|---|
| **Pracownicy** | Zaimportowani pracownicy, Lista APT |
| **Plany dzienne** | Plany dzienne |
| **Import danych** | Import planu zmianowego, Import pracowników, Import pracowników APT |
| **Stanowiska** | Lista stanowisk |
| **Przydziały** | Dashboard obsady, Historia przydziałów |
| **Raporty** | Raport obsady (Excel) |
| **Administracja** | Panel admina (tylko rola `admin`) |

Przycisk „Zwiń" zwija sidebar do ikon (56 px); stan w `localStorage`.

---

## 6. Algorytm przydziału pracowników

Funkcja `_wykonaj_przydzial(plan: PlanDzienny) -> dict` w `apps/pracownicy/views.py`.

### 6.1 Dane wejściowe

- `ZapotrzebowanieGodzinowe` dla planu → `plan_godziny: {(akt_pk, zmiana): {godzina: liczba_osob}}`
- `Pracownik.objects.all()` — wszyscy pracownicy etatowi
- `KompetencjaPracownika` filtrowana do aktywności w planie → `komp_map: {pracownik_pk: set(aktywnosc_pk)}`
- `PracownikAPT` + `OcenaAPT` → `comp_apt: {(apt_pk, akt_pk): max_ocena}`
- `AbsencjaPracownika` dla `plan.data_planu` → `nieobecni_pks: set[int]`

### 6.2 Pojemność aktywności

```python
capacity = math.ceil(max(hourly_values))
```

Szczyt zapotrzebowania godzinowego zaokrąglony w górę.

### 6.3 Podział na zmiany

| Zmiana | Litera | Godziny |
|---|---|---|
| I | A | 6–13 |
| II | B | 14–21 |
| III | C | 22–23, 0–5 |

Pracownik trafia do zmiany gdy jego `zmiana_grupa` zaczyna się na odpowiednią literę (A/B/C). Pracownicy bez `zmiana_grupa` przydzielani są do pierwszej zmiany, w której jeszcze nie figurują (`globally_assigned_prac` — deduplication).

### 6.4 Kolejność wypełniania do `capacity`

1. **Pracownicy priorytetowi** (`departament` ∈ {`IN`, `OB`, `FF`, `ZW`, `PR`}) pasujący do aktywności
2. **Pozostali pracownicy** pasujący do aktywności
3. **Pracownicy APT** sortowani malejąco wg oceny dla tej aktywności

### 6.5 Kryteria dopasowania pracownika do aktywności (`_pasuje_do_aktywnosci`)

Pracownik pasuje jeśli spełniony **co najmniej jeden** warunek:

| Kryterium | Sprawdzenie |
|---|---|
| Stanowisko | `p.stanowisko.lower() == aktywnosc.nazwa.lower()` |
| Dział | `p.dzial` zawiera lub jest zawarty w `aktywnosc.dzial` (case-insensitive) |
| Departament | Słowa kluczowe `_DEPT_KEYWORDS[departament]` są w `aktywnosc.dzial` |
| Kompetencja | `aktywnosc.pk ∈ komp_map[pracownik.pk]` (wynik > 0 w KOMPETENCJE) |

**Słowa kluczowe departamentów:**
```python
_DEPT_KEYWORDS = {
    'IN': ['in', 'ib', 'inbound', 'przej', 'odbi'],
    'OB': ['ob', 'outbound', 'ekspedy', 'wysy'],
    'FF': ['ff', 'fulfil', 'kompl'],
    'ZW': ['zw', 'zwrot', 'return'],
    'PR': ['pr', 'prasa', 'press'],
}
```

### 6.6 Force-assign

Priorytetowi pracownicy, którym nie przydzielono żadnej aktywności (po głównej pętli), są force-assign'owani do pierwszej aktywności pasującej przez dział, departament lub kompetencję.

### 6.7 Fillers

Pracownicy z danej zmiany, którym mimo force-assign nie znaleziono aktywności, lądują w kategorii `(bez przypisanej aktywności)` wyświetlanej na dole zakładki zmiany.

### 6.8 Struktura JSON `PrzydzialDzienny.dane`

```json
{
  "1": {                          // klucz = numer zmiany
    "<akt_pk>": {
      "nazwa": "Picking",
      "dzial": "Outbound",
      "wymagana": 5,
      "pracownicy": [
        {
          "pk": 42,
          "imie": "Jan",
          "nazwisko": "Kowalski",
          "zmiana_grupa": "A-1",
          "nieobecny": false,
          "wynik": null,
          "zapychacz": false,
          "apt": false
        }
      ],
      "godziny": {"6": 3.0, "7": 5.0, "8": 5.0, "9": 4.0, "10": 3.0, "11": 2.0, "12": 2.0, "13": 1.0}
    },
    "__fillers__": { ... }
  },
  "2": { ... },
  "3": { ... }
}
```

---

## 7. Routing URL

```
/                                               → redirect do /konta/dashboard/
/admin/                                         → panel administracyjny Django

/konta/login/                                   → logowanie
/konta/logout/                                  → wylogowanie
/konta/dashboard/                               → przekierowanie po roli

/pracownicy/                                    → lista pracowników
/pracownicy/<pk>/usun/                          → usuń pracownika (POST)
/pracownicy/usun-wszystkich/                    → usuń wszystkich (POST)
/pracownicy/<pk>/kompetencje/                   → kompetencje pracownika (JSON, AJAX)
/pracownicy/apt/                                → lista pracowników APT
/pracownicy/plany/                              → lista planów dziennych
/pracownicy/plany/<pk>/usun/                    → usuń plan (POST)
/pracownicy/plany/<pk>/przydziel/               → uruchom przydział (POST)
/pracownicy/plany/<pk>/wyniki/                  → wyniki przydziału (GET)

/import/plan-zmianowy/                          → import planu zmianowego
/import/pracownicy/                             → import pracowników
/import/pracownicy-apt/                         → import pracowników APT

/stanowiska/                                    → lista stanowisk
/stanowiska/<pk>/                               → podgląd stanowiska
/stanowiska/dodaj/                              → dodaj stanowisko
/stanowiska/<pk>/edytuj/                        → edytuj stanowisko
/stanowiska/<pk>/usun/                          → usuń stanowisko (POST)

/przydzialy/                                    → dashboard obsady (legacy)
/przydzialy/historia/                           → historia przydziałów (legacy)

/raporty/obsada/excel/                          → raport Excel
```

**Namespace `pracownicy`** — URL-e `/pracownicy/*`
**Namespace `import_danych`** — URL-e `/import/*`

---

## 8. Konfiguracja i zmienne środowiskowe

Plik `.env` w katalogu głównym:

```env
DEBUG=True
SECRET_KEY=<losowy-klucz-django>
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
FIELD_ENCRYPTION_KEY=<klucz-fernet-base64>
```

### Generowanie kluczy

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())          # FIELD_ENCRYPTION_KEY

from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())                 # SECRET_KEY
```

---

## 9. Uruchomienie projektu

### Wymagania

- Python 3.10+
- Windows (PDF korzysta z `C:/Windows/Fonts/arial.ttf`)
- Środowisko wirtualne (`myvenv`)

### Instalacja

```bash
# Aktywacja venv (Windows)
C:\Odzyskane\PythonVSFolder\.vscode\My_Django_Projects\myvenv\Scripts\activate

pip install -r requirements.txt

# Uzupełnij .env (sekcja 8)

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Aplikacja: `http://127.0.0.1:8000/`

Katalog `tmp/` tworzony automatycznie przez `_tmp_dir()`.

---

## 10. Format plików do importu

### 10.1 Plan dzienny — `Plan_dzienny_NEW.xlsx`

| Kolumna | Indeks (0-based) | Zawartość |
|---|---|---|
| A | 0 | Nazwa aktywności |
| B | 1 | `'Bufor'` — wiersz nagłówka działu |
| C | 2 | Wolumen |
| L–S | 11–18 | Zmiana I, godziny 6–13 |
| W–AD | 22–29 | Zmiana II, godziny 14–21 |
| AH–AO | 33–40 | Zmiana III, godziny 22–23, 0–5 |

---

### 10.2 Macierz kompetencji — `KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx`

- Wiersze 3–5 (1-indexed): 3-poziomowy nagłówek (dział / poddział / aktywność), scalone komórki → forward-fill
- Wiersz 6: etykiety kolumn pracownika (A–N, indeksy 0–13)
- Kolumny 0–13: dane pracownika (indeks 11 = `zmiana_grupa`)
- Kolumny 14+: aktywności, wartość = ocena (tylko > 0 zapisywana)
- Pomijane: kolumny z `'prasa'` w nazwie działu

---

### 10.3 Struktura i absencje — `Struktura___Grafik___Absencje_NEW.xlsx`

- Arkusze: `Struktura IB`, `Struktura OB`, `Struktura FF`, `Struktura PR`, `Struktura ZW`
- Wiersz 6 = nagłówki (`Nazwisko`, `Imię`, `Zmiana grupa`, `Zmiana`, daty absencji…)
- Wiersz 7+ = dane pracowników
- Kolumny z datą `DD.MM.YYYY` w nagłówku → `AbsencjaPracownika`
- Typy absencji z arkusza `Listy Rozwijane`, kolumna B

---

### 10.4 Pracownicy APT — `PracownicyAPT*.xlsx`

Arkusz `PracownicyAPT01`:

| Indeks (0-based) | Zawartość |
|---|---|
| 0 | Imię |
| 1 | Nazwisko |
| 7 | Nazwa agencji |
| 11 | Płeć |
| 12 | Grupa |
| 2,3,4,5,6,8,9,10,13–18 | Oceny → kolumny APT 1–14 |

---

## 11. Znane ograniczenia

| Kwestia | Status |
|---|---|
| Obsada stanowisk w `/stanowiska/` i `/przydzialy/` | Stub (0) — stary model `PlanZmiany` usunięty, integracja z nowym systemem nie zaimplementowana |
| Raport Excel (`/raporty/obsada/excel/`) | Może wymagać aktualizacji pod nowy schemat modeli |
| Fuzzy-matching nazw aktywności | Nie ma. Nazwy w planie muszą być identyczne z nazwami w KOMPETENCJE lub dopasowywane przez dział/departament/kompetencje |
| Absencje dla planów bez `data_planu` | Nie są sprawdzane — flaga `nieobecny` zawsze `False` |

---

*Dokumentacja zaktualizowana: 2026-07-04 | System Magazynowy v2.1*
