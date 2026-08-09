# System Magazynowy — Dokumentacja projektu

## Spis treści

1. [Przegląd systemu](#1-przegląd-systemu)
2. [Stos technologiczny](#2-stos-technologiczny)
3. [Struktura projektu](#3-struktura-projektu)
4. [Baza danych — modele](#4-baza-danych--modele)
5. [Moduły i funkcje](#5-moduły-i-funkcje)
6. [Algorytm przydziału pracowników](#6-algorytm-przydziału-pracowników)
7. [Macierz procesowa i fuzzy-matching](#7-macierz-procesowa-i-fuzzy-matching)
8. [System modali — wyniki_przydzialu.html](#8-system-modali--wyniki_przydzialhtml)
9. [Routing URL](#9-routing-url)
10. [Konfiguracja i zmienne środowiskowe](#10-konfiguracja-i-zmienne-środowiskowe)
11. [Bezpieczeństwo](#11-bezpieczeństwo)
12. [Uruchomienie projektu](#12-uruchomienie-projektu)
13. [Format plików do importu](#13-format-plików-do-importu)
14. [Znane ograniczenia](#14-znane-ograniczenia)

---

## 1. Przegląd systemu

System Magazynowy to aplikacja webowa zbudowana w Django 5.2, przeznaczona do zarządzania pracownikami magazynowymi — importu danych kadrowych, planów zapotrzebowania godzinowego, macierzy kompetencji oraz automatycznego przydziału pracowników do aktywności.

**Główny przepływ pracy:**

1. **Import planu dziennego** — wgraj plik `Plan_dzienny_NEW.xlsx`; parser odczytuje zapotrzebowanie godzinowe na 3 zmiany i zapisuje rekordy `ZapotrzebowanieGodzinowe`
2. **Import pracowników** — wgraj plik `KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx` i/lub `Struktura___Grafik___Absencje_NEW.xlsx`; dane scalane w profil pracownika wraz z `zmiana_grupa`
3. **Import pracowników APT** — skonfiguruj mapowanie kolumn 1–14 na działy, wgraj plik z ocenami
4. **Przydział pracowników** — kliknij „Przydziel" na planie; algorytm przydziela pracowników do aktywności według zmian, kompetencji i priorytetu (etatowi przed APT)
5. **Wyniki przydziału** — tabela z zakładkami zmian (I/II/III/D), tabelami godzinowymi (Plan/Fakt), listą pracowników z kolorowym badge'em grupy zmiany, wskaźnikiem nieobecności oraz sekcją nieprzypisanych z wyjaśnieniem przyczyn

Dostęp do wszystkich widoków wymaga zalogowania. Parser nie korzysta z AI — wszystkie kolumny rozpoznawane są deterministycznie, czyli że parser rozpoznaje kolumny na podstawie stałych, z góry zaprogramowanych reguł — a nie "zgadywania". W praktyce oznacza to, że dla tych samych danych wejściowych parser zawsze da dokładnie ten sam wynik. Typowe mechanizmy takiego rozpoznawania kolumn:

dopasowanie nazw nagłówków do listy znanych wzorców (np. "Imię i nazwisko", "Nr pracownika", "Zmiana" — z uwzględnieniem wariantów pisowni)
dopasowanie po pozycji/kolejności kolumn
dopasowanie po typie danych (np. kolumna z samymi datami, kolumna z liczbami w określonym zakresie)
reguły regex / warunki if-else

---

## 2. Stos technologiczny

Backend: Django 5.2, Python 3.13


Baza danych: SQLite (dev) → PostgreSQL (prod)


Frontend: Bootstrap 5.3 + Bootstrap Icons 1.11
          Vanilla JS (bez frameworka)

Obsługa plików: Excel (odczyt): openpyxl 3.1.5
                PDF: reportlab, czcionka Arial z C:/Windows/Fonts

Bezpieczeństwo i konfiguracja

Szyfrowanie pól: django-encrypted-model-fields 0.6.5 + cryptography
Zmienne środowiskowe: django-environ 0.11.2
Rate limiting logowania: django-axes 8.3.1

Infrastruktura

Serwowanie plików statycznych: WhiteNoise 6.8.2

Logika biznesowa

Optymalizacja przydziału: networkx 3.4.2 (min-cost flow — szczegóły w sekcji 6)4 |

> **Uwaga:** OpenAI API zostało usunięte w wersji 2.0 (2026-07-04). Pakiety `openai` i `httpx` usunięte z `requirements.txt` w v2.4.
>
> **Uwaga:** projekt ma dwa środowiska wirtualne — `magazyn\.venv` oraz współdzielone
> `myvenv` katalog wyżej (`My_Django_Projects\myvenv`). Przed instalacją nowej zależności
> upewnij się, którego środowiska faktycznie używa uruchomiony serwer/IDE — `pip install`
> w niewłaściwym venvie kończy się sukcesem po cichu, a serwer i tak nie znajdzie pakietu
> przy starcie (`ModuleNotFoundError`).

---

## 3. Struktura projektu

```
magazyn/
├── apps/
│   ├── konta/              # Uwierzytelnianie i role użytkowników
│   │   ├── decorators.py   # Decoratory dostępu: wymaga_roli, tylko_hr, tylko_kierownik
│   │   ├── models.py       # Model Profil (rola użytkownika)
│   │   └── tests.py        # Testy kontroli dostępu
│   ├── pracownicy/         # Główny moduł: pracownicy, import, plany, przydział
│   │   ├── parsers/        # Deterministyczne parsery Excel
│   │   │   ├── plan_dzienny.py       # Parser Plan_dzienny_NEW.xlsx
│   │   │   ├── kompetencje.py        # Parser KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx
│   │   │   ├── struktura.py          # Parser Struktura___Grafik___Absencje_NEW.xlsx
│   │   │   └── pracownicy_apt.py     # Parser PracownicyAPT*.xlsx
│   │   ├── management/commands/
│   │   │   └── cleanup_tmp_imports.py  # Kasuje tmp/*.json starsze niż N godzin
│   │   ├── templatetags/
│   │   │   └── pracownicy_extras.py  # Filtr get_item dla słowników w szablonach
│   │   ├── migrations/
│   │   ├── models.py
│   │   ├── validators.py             # waliduj_plik_importu() — rozszerzenie + rozmiar
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
│       ├── brak_dostepu.html         # Strona 403
│       └── zablokowany.html          # Strona blokady axes (429)
├── tmp/                    # Pliki tymczasowe podglądu importu (UUID.json) — nieserwowalny
├── .env
├── .env.example            # Szablon zmiennych środowiskowych (bez wartości)
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
| `departament` | CharField(20, blank) | Kod departamentu: `IN`, `OB`, `FF`, `ZW`, `PR` (etatowi priorytetowi) lub `APT 1`–`APT 4` (agencyjni) |
| `stanowisko` | CharField(100, blank) | Stanowisko |
| `strefa` | CharField(50, blank) | Strefa magazynowa |
| `dzial` | CharField(100, blank) | Dział (z pliku struktury) |
| `zmiana` | CharField(5, blank) | Zmiana (np. `I`, `II`, `III`) |
| `zmiana_grupa` | CharField(10, blank) | Grupa zmiany (np. `A-1`, `B-2`, `C-3`, `D-2`) |
| `przelozony` | CharField(100, blank) | Przełożony |
| `komentarz` | TextField(blank) | Komentarz |
| `data_zatrudnienia` | DateField(null) | Data zatrudnienia |
| `arkusz` | CharField(50, blank) | Nazwa arkusza źródłowego z pliku Struktury (np. `Struktura FF`) |

**Import:** każdy import zastępuje wszystkich pracowników (`Pracownik.objects.all().delete()` + `bulk_create`).

**Źródło `departament`:** kolumna 0 pliku KOMPETENCJE. Pracownicy agencyjni mają `departament` = `APT 1`/`APT 2`/`APT 3`/`APT 4` — są wykluczani z puli etatowych w algorytmie przydziału.

**Źródło `arkusz`:** nazwa arkusza w pliku Struktury (np. `Struktura IB`, `Struktura FF`). Używane do wyświetlania skrótu sektora w wynikach przydziału.

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

### 4.11 `pracownicy.KonfiguracjaZmian`

Singleton (pk=1). Mapuje numery zmian na litery grup pracowniczych.

| Pole | Typ | Domyślna | Opis |
|---|---|---|---|
| `zmiana_1` | CharField(1) | `A` | Litera grupy dla Zmiany I (6–13) |
| `zmiana_2` | CharField(1) | `B` | Litera grupy dla Zmiany II (14–21) |
| `zmiana_3` | CharField(1) | `C` | Litera grupy dla Zmiany III (22–5) |
| `zmiana_4` | CharField(1) | `D` | Litera grupy dla Zmiany D (PRASA/KDR) |

Metoda `pobierz()` — `get_or_create(pk=1)`. Metoda `jako_slownik()` → `{1: 'A', 2: 'B', 3: 'C', 4: 'D'}`.

---

### 4.12 `stanowiska.Stanowisko`

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

### 4.13 `konta.Profil`

| Pole | Typ | Opis |
|---|---|---|
| `user` | OneToOne(User) | Django User |
| `rola` | CharField | `admin`, `hr`, `kierownik` |

---

## 5. Moduły i funkcje

### 5.1 Moduł `pracownicy`

#### Lista pracowników (`/pracownicy/`)

Tabela pracowników z filtrami i paginacją (50 na stronę).

**Kolumny tabeli:**

| Kolumna | Opis |
|---|---|
| Nr ewid. | Numer ewidencyjny |
| Nazwisko / Imię | Dane osobowe |
| **Przynależność** | Badge `Etat` (zielony) lub `APT` (żółty) — na podstawie `departament` pracownika |
| Data zatr. | Data zatrudnienia |
| Stanowisko | Stanowisko (z tooltipem) |
| Strefa | Strefa magazynowa |
| Dział | Badge z popoverem top 4 kompetencji (hover) |
| Zmiana / Gr. zm. | Zmiana i grupa zmiany |
| Przełożony | Imię i nazwisko przełożonego |
| Absencje | Daty absencji (max 3 + licznik nadmiarowych) |
| Komp. | Liczba kompetencji; kliknij → modal AJAX z pełną listą |

**Filtry:**

- **Pole tekstowe** — filtruje po imieniu lub nazwisku (debounced, 360 ms)
- **Zakładki arkuszy** — zawęża do pracowników z danego arkusza Struktury (IN/IB/OB/FF/ZW/PR)
- **Tylko z absencjami** — toggle; pokazuje tylko pracowników z co najmniej jedną absencją
- **Typ: Etat / APT** — dwa checkboxy obok toggle'a absencji:
  - zaznaczony tylko `Etat` → tylko etatowi (wyklucza `departament` = `APT*`)
  - zaznaczony tylko `APT` → tylko agencyjni
  - oba lub żaden → wszyscy
- **Filtry kolumnowe** (wiersz pod nagłówkami) — zawężają po każdej kolumnie osobno

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

- **Podsumowanie** — cztery kafelki (Zmiana I/II/III/D) z liczbą przypisanych i nieprzypisanych
- **Zakładki** — osobna zakładka na każdą zmianę (Zm. I, Zm. II, Zm. III, Zm. D) z liczbą pracowników w badge
- **Na każdą aktywność:**
  - Nagłówek: nazwa, ikona ostrzeżenia przy niedoborze, badge `przydzielono / wymagana`
  - Tabela godzinowa „Plan / Fakt": kolumny = godziny zmiany; „Plan" = wymagana liczba (komórki czerwone przy niedoborze), „Fakt" = faktyczna obsada
  - Lista pracowników: badge z grupą zmiany (A=zielony, B=niebieski, C=czerwony, D=fioletowy), badge APT (żółty), tooltip z pełnym imieniem, grupą i literą `N` dla nieobecnych
- **„(bez przypisanej aktywności)"** — sekcja fillers z wyjaśnieniami i podziałem Etatowi/APT (szczegóły poniżej)

**Sekcja „bez przypisanej aktywności" (fillers):**

- **Legenda powodów** (nad listą): liczba pracowników nieobecnych / z zapełnionymi aktywnościami / bez dopasowania
- **Etatowi** — pracownicy etatowi podzieleni per powód:
  - Badge czerwony (`background:#fee2e2`) + `(N)` — nieobecny w dniu planu
  - Badge pomarańczowy (`background:#ffedd5`) — pasuje do aktywności, ale wszystkie pełne
  - Badge szary (`bg-light`) — brak dopasowania do żadnej aktywności zmiany
  - Skrót sektora (np. `FF`, `OB`, `IN`) wyświetlany jako mały szary chip; pełna info w tooltipie
- **APT** — pracownicy agencyjni z żółtym badge'em (`background:#fefce8`), powód w tooltipie

---

#### Import planu zmianowego (`/import/plan-zmianowy/`)

Dwuetapowy (upload → podgląd → zatwierdź). Zapisuje `PlanDzienny` + rekordy `ZapotrzebowanieGodzinowe` przez `bulk_create`. Pliki tymczasowe w `tmp/<UUID>.json`.

---

#### Import pracowników (`/import/pracownicy/`)

Dwuetapowy import z opcjonalnymi dwoma plikami.

**Scalanie danych:** `pracownicy_dict[key] = {**kompetencje_dane, **struktura_dane}` — struktura nadpisuje kompetencje dla tych samych kluczy `(nazwisko, imie)`. `zmiana_grupa` czytana z obu plików.

Po zatwierdzeniu: `Pracownik.objects.all().delete()` + `bulk_create` pracowników, kompetencji, absencji.

> **Uwaga:** Plik Struktury zawiera zarówno pracowników etatowych (arkusze `Struktura IN/OB/FF/ZW/PR`) jak i agencyjnych (ci z `departament = APT*`). Algorytm przydziału wykluwa agencyjnych z puli etatowej i obsługuje ich osobno przez model `PracownikAPT`.

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
- Kolumny 0–13: dane pracownika (w tym indeks 0 = `departament`, indeks 11 = `zmiana_grupa`)
- `_forward_fill()` dla scalonych komórek nagłówkowych
- Kolumny 14+: aktywności; tylko `wynik > 0` zapisywany
- Pomija kolumny z `'prasa'` w nazwie działu

#### `struktura.py`
- Arkusze: `Struktura IB/OB/FF/PR/ZW`
- Wiersz 6 (1-indexed) = nagłówki, wiersz 7+ = dane
- Daty w nagłówkach → rekordy absencji; typy z arkusza `Listy Rozwijane` col B
- Zapisuje `_sheet` = nazwę arkusza → pole `Pracownik.arkusz` (np. `Struktura FF`)

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

Funkcja `_wykonaj_przydzial(plan: PlanDzienny) -> dict` w `apps/pracownicy/views.py` — od
2026-08-03 jest to **orchestrator**, nie sam algorytm. Właściwy silnik (przepływ o
minimalnym koszcie, NetworkX) znajduje się w `apps/pracownicy/przydzial_flow.py`. Poprzednia
wersja (zachłanny algorytm fazowy: tier1/tier2/force-assign) została w całości zastąpiona —
opis poniżej odzwierciedla nowy silnik. Testy jednostkowe i integracyjne: `apps/pracownicy/tests.py`.

### 6.0 Przegląd end-to-end: jak system dopasowuje pracownika do aktywności

Dwa niezależne źródła danych muszą zostać ze sobą zsynchronizowane, zanim jakiekolwiek
dopasowanie się odbędzie:

1. **`/pracownicy/`** — lista pracowników, każdy z polem `Pracownik.dzial` (dział, do którego
   przypisany jest w danych kadrowych) oraz `zmiana`/`zmiana_grupa` (przypisana zmiana).
2. **`/pracownicy/plany/<id_planu>/`** — plan zmianowy zaimportowany z Excela: dla każdej
   `Aktywnosc` (nazwa + `dzial` — to jest odpowiednik "nagłówka kolumny" z arkusza planu),
   godzinowe zapotrzebowanie (`ZapotrzebowanieGodzinowe`) per zmiana (1/2/3).

Nazewnictwo działów w tych dwóch źródłach **nie musi być identyczne** (literówki, skróty,
różna wielkość liter) — stąd potrzeba fuzzy-matchingu opisanego w sekcji 6.4. Przebieg
pełnego przydziału, krok po kroku:

```
┌─────────────────────┐        ┌──────────────────────────────┐
│  Pracownik.dzial     │        │  Aktywnosc.dzial              │
│  (/pracownicy/)      │        │  (/pracownicy/plany/<id>/)    │
└──────────┬───────────┘        └───────────────┬───────────────┘
           │                                     │
           └───────────────┬─────────────────────┘
                            ▼
              buduj_crosswalk_dzialow()            (raz na cały przebieg,
              fuzzy match: substring → difflib          patrz 6.4)
              próg 0.85, strefa niepewności 0.70-0.85 → log ostrzeżenia
                            │
                            ▼
        dla każdego "bucketu" zmiany (1, 2, 3, D, bez-zmiany, leftover-APT):
                            │
              ┌─────────────┴──────────────┐
              ▼                             ▼
     P1: pasuje_zmiana()          shift_acts: (akt_pk, capacity=
     — filtruje WĘZŁY,              ceil(max godzinowego
     nie krawędzie o wysokim         zapotrzebowania), godziny)
     koszcie (6.3)
              │                             │
              └─────────────┬───────────────┘
                            ▼
              buduj_graf_zmiany() / rozwiaz_zmiane()
              graf: źródło → pracownik (cap=1) → aktywność (cap=wymagana) → ujście
              koszt krawędzi = koszt_dopasowania() → P2 (dział) + P3 (kompetencja)  (6.4)
                            │
                            ▼
              networkx.max_flow_min_cost(graf, źródło, ujście)
              1. maksymalizuj LICZBĘ przydzieleń
              2. dopiero wśród maksimów — minimalizuj SUMĘ kosztów
                            │
                            ▼
              dekoduj przepływ → dla każdej pary (pracownik, aktywność)
              z przepływem ≥ 1: zapisz {pk, wynik, dzial_ok, fuzzy_score,
              kompetencja_uzyta, apt: False}
                            │
                            ▼
              druga runda: APT na pojemności resztkowej
              (wymagana − już_przydzieleni), ta sama koszt_dopasowania(),
              etat ZAWSZE ma pierwszeństwo (6.4)
                            │
                            ▼
              PrzydzialDzienny.dane[str(zmiana)][str(akt_pk)] = {...}
```

**Konkretny przykład liczbowy** (ilustracja modelu kosztów, nie prawdziwe dane):

Aktywność „Kompletacja Retail" (dział `Outbound`, zmiana A, `wymagana = 1`). Trzech
kandydatów przeszło już P1 (wszyscy mają zmianę A):

| Pracownik | `dzial` | dopasowanie do `Outbound` | ocena kompetencji | koszt krawędzi |
|---|---|---|---|---|
| Jan | `Outbound` | substring, `dzial_ok=True` | 45/50 → 9/10 | `10 − 9 = 1` |
| Anna | `Wysyłka` | fuzzy 0.91 ≥ 0.85, `dzial_ok=True` | 20/50 → 4/10 | `10 − 4 = 6` |
| Piotr | `Inbound` | brak dopasowania, `dzial_ok=False` | 50/50 → 10/10 | `10000 + (10 − 10) = 10000` |

Mimo że Piotr ma **najwyższą** kompetencję, jego koszt jest o cztery rzędy wielkości wyższy
niż u Jana czy Anny — `max_flow_min_cost` wybierze Jana (koszt 1, najniższy). Piotr zostałby
przydzielony **wyłącznie** gdyby Jan i Anna w ogóle nie istnieli jako kandydaci (P1 wykluczyłby
ich albo capacity zostałaby wyczerpana) — wtedy i tylko wtedy przepływ o maksymalnej liczbie
przydzieleń wymusi użycie Piotra, płacąc karę 10000 (dopasowanie awaryjne, `dzial_ok=False`
widoczne w wyniku do celów audytu).

Pełny, sformalizowany opis każdego kroku — w sekcjach 6.1–6.8 poniżej.

### 6.1 Dane wejściowe

- `ZapotrzebowanieGodzinowe` dla planu → `plan_godziny: {(akt_pk, zmiana): {godzina: liczba_osob}}`
- `Pracownik.objects.all()` filtrowany do etatowych (wyklucza `departament` zaczynające się od `APT`) → `pracownicy`
- `KompetencjaPracownika` filtrowana do aktywności w planie → `komp_map: {pracownik_pk: set(aktywnosc_pk)}`
- `PracownikAPT` + `OcenaAPT` → `comp_apt: {(apt_pk, akt_pk): max_ocena}`
- `AbsencjaPracownika` dla `plan.data_planu` → `nieobecni_pks: set[int]`

### 6.1a Rozróżnienie etatowi / APT

Pula etatowych (`pracownicy`) obejmuje wyłącznie rekordy `Pracownik` z `departament` **nie** zaczynającym się od `'APT'`. Pracownicy z `departament = APT 1/2/3/4` (z pliku KOMPETENCJE) są pomijani w tej puli — obsługuje ich model `PracownikAPT`.

```python
pracownicy = [
    p for p in Pracownik.objects.all()
    if not p.departament.strip().upper().startswith('APT')
]
```

### 6.1b Macierz procesowa w przydziale

Algorytm używa `worker_group_score[(worker_pk, plan_akt_pk)]` — średniej oceny pracownika ze wszystkich czynności w grupach procesowych dopasowanych fuzzy do danej aktywności planu. Szczegóły w sekcji 7.

### 6.2 Pojemność aktywności

```python
capacity = math.ceil(max(hourly_values))
```

Szczyt zapotrzebowania godzinowego zaokrąglony w górę.

### 6.3 Podział na zmiany

| Zmiana | Litera | Godziny | Typ |
|---|---|---|---|
| I | A | 6–13 | Standardowa |
| II | B | 14–21 | Standardowa |
| III | C | 22–23, 0–5 | Standardowa |
| D | D | Zmienne | PRASA/KDR (specjalna) |

Pracownik trafia do zmiany gdy `pasuje_zmiana(pracownik, litera)` zwraca `True` (dokładne
dopasowanie pola `zmiana`, albo `zmiana_grupa` zaczynająca się od tej litery). Pracownicy bez
`zmiana` I bez `zmiana_grupa` ("bez zmiany") są **świadomie zwolnieni** z tego wymogu (patrz
6.4) — wypełniają resztkową pojemność zmian I–III w osobnym przebiegu po głównych zmianach,
zamiast rezerwować sobie "pierwszą zmianę, w której jeszcze nie figurują" jak w starej wersji.

**Obsługa absencji:** pracownicy z `pk ∈ nieobecni_pks` są **wykluczeni** — nie wchodzą jako
węzły do grafu przepływu tej zmiany. Trafiają bezpośrednio do sekcji fillers z flagą
`nieobecny=True` (raz na plan — `globally_absent_shown` zapobiega duplikatom między zmianami).

### 6.4 Hierarchia priorytetów P1/P2/P3 — min-cost flow (NetworkX)

Silnik: `apps/pracownicy/przydzial_flow.py`. Kolejność priorytetów jest **leksykograficzna** —
wyższy priorytet całkowicie dominuje nad niższym, to nie jest suma ważona kilku kryteriów.

**P1 — zgodność zmiany, warunek bezwzględny (`pasuje_zmiana`):**
Decyduje, czy krawędź pracownik→aktywność w ogóle istnieje w grafie przepływu dla danego
"bucketu" zmiany. Brak zgodności = brak krawędzi, nigdy wysoki koszt — dzięki temu pracownik
z niepasującą zmianą nie może zostać przydzielony nawet jako ostateczność, gdyby był jedynym
kandydatem.

**P2 — zgodność działu, miękka ale dominująca (`koszt_dopasowania` + `dzialy_fuzzy_match`):**
Fuzzy dopasowanie `Pracownik.dzial` do `Aktywnosc.dzial` przez `difflib.SequenceMatcher`
(próg akceptacji 0.85; wynik w [0.70, 0.85) logowany jako ostrzeżenie do ręcznej weryfikacji,
nie akceptowany ani odrzucany po cichu) **LUB** dotychczasowe dopasowanie kodu departamentu
przez słowa kluczowe (`_dept_matches_akt`, patrz niżej — zachowane, żeby nie zepsuć
istniejących przydziałów pracowników priorytetowych). Niezgodność dodaje do kosztu krawędzi
`PRZYDZIAL_PENALTY_DZIAL` (domyślnie 10 000) — na tyle dużo, że żadna kombinacja ocen
kompetencji (P3, zakres 0–`PRZYDZIAL_KOSZT_MAX_KOMPETENCJI`, domyślnie 10) nie może tego
przebić.

**P3 — ocena kompetencji:**
Różnicuje wyłącznie pomiędzy pracownikami, którzy już przeszli P1 i mają ten sam status P2.
Koszt = `KOSZT_MAX_KOMPETENCJI - ocena_znormalizowana`. Brak wpisu kompetencji nie wywala
wyjątku — liczony jako najniższa ocena (0) plus mała dodatkowa kara
`PRZYDZIAL_BRAK_KOMPETENCJI_PENALTY` (domyślnie 1), wciąż dużo mniejsza niż `PENALTY_DZIAL`.

**Rozwiązanie:** `rozwiaz_zmiane()` buduje graf (źródło → pracownicy, pojemność 1 każdy →
aktywności, pojemność = `wymagana` → ujście) i woła `networkx.max_flow_min_cost`, który
**najpierw maksymalizuje liczbę przydzieleń**, a dopiero wśród rozwiązań maksymalnych
minimalizuje koszt. To zastępuje dawny osobny "force-assign": pracownik priorytetowy bez
dopasowania działu i tak dostanie przydział (płacąc karę P2), jeśli to jedyny sposób
wypełnienia wolnego miejsca — bez dodatkowego przebiegu w kodzie.

**Etatowi zawsze przed APT — decyzja świadoma, nie ograniczenie modelu:** każdy "bucket"
zmiany rozwiązywany jest jako **dwa kolejne** przepływy: najpierw etatowi, potem APT na
pozostałej (resztkowej) pojemności (`wymagana - już_przydzieleni`). Dobrze dopasowany
pracownik APT nigdy nie wyprze słabiej dopasowanego etatowego — potwierdzone z użytkownikiem
jako świadomy wybór, alternatywą było jedno wspólne rozwiązanie z etatowymi i APT
konkurującymi na równych zasadach.

**Pola audytowe** (nowe, na każdym realnym przydziale): `dzial_ok` (bool), `fuzzy_score`
(float), `kompetencja_uzyta` (float użyta do kosztu) — pozwalają odróżnić "dopasowanie
idealne" od "dopasowania awaryjnego" (zmiana OK, dział niezgodny, użyty tylko bo brakowało
innych kandydatów). Nie są jeszcze wyświetlane w `wyniki_przydzialu.html` — szablon czyta
tylko nazwane atrybuty, więc nowe pola są bezpieczne, tylko na razie nieużywane przez UI.

### 6.5 Kryteria klasyfikacji fillerów (`_pasuje_do_aktywnosci`)

Ta funkcja **nie decyduje już o przydziale** (to robi P1/P2/P3 wyżej) — służy wyłącznie do
klasyfikacji powodu w sekcji fillers (`capacity` vs `no_match`, patrz 6.7). Pracownik "pasuje"
jeśli spełniony **co najmniej jeden** warunek:

| Kryterium | Sprawdzenie |
|---|---|
| Stanowisko | `p.stanowisko.lower() == aktywnosc.nazwa.lower()` |
| Dział | `p.dzial` zawiera lub jest zawarty w `aktywnosc.dzial` (case-insensitive) |
| Departament | Słowa kluczowe `_DEPT_KEYWORDS[departament]` są w `aktywnosc.dzial` |
| Kompetencja | `aktywnosc.pk ∈ komp_map[pracownik.pk]` (wynik > 0 w KOMPETENCJE) |

Ten sam departament-keyword check (`_dept_matches_akt`) jest też jedną z dwóch ścieżek P2
opisanych w 6.4 — nie jest to duplikat przypadkowy, tylko świadome dzielenie logiki między
"czy to jest realne dopasowanie działu" (P2, koszt) i "jak nazwać powód fillera" (6.7,
wyłącznie kosmetyczne).

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

### 6.6 Zmiana D (PRASA/KDR)

Przetwarzana osobno, po pętli zmian I–III. Obejmuje aktywności z działów PRASA i KDR, dopasowane przez grupy procesowe nr 24 (PRASA) i 56 (KDR) oraz filtr słów kluczowych `{'kdr', 'zwrot', 'prasa'}` w nazwie działu.

Pracownicy z `zmiana_grupa` zaczynającą się od litery D (konfigurowalnej w `KonfiguracjaZmian.zmiana_4`). Silnik wewnętrzny identyczny jak dla zmian I–III — ten sam `rozwiaz_zmiane()` i hierarchia P1/P2/P3 opisana w 6.4, tylko zbiór aktywności i pracowników ograniczony do PRASA/KDR.

Wyniki w `PrzydzialDzienny.dane` pod kluczem `"4"`.

### 6.7 Fillers i powody nieprzypisania

Pracownicy, którym nie przydzielono żadnej aktywności, lądują w `__fillers__`. Każdy filler ma pole `powod`:

| Powód | Znaczenie |
|---|---|
| `nieobecny` | Pracownik nieobecny w dniu planu (absencja) |
| `capacity` | Pasuje do co najmniej jednej aktywności, ale wszystkie są pełne |
| `no_match` | Nie pasuje do żadnej aktywności tej zmiany |
| `no_activities` | Zmiana nie ma żadnych aktywności w planie |

Pole `sektor` fillerów etatowych: skrót sektora wyciągany z `Pracownik.arkusz` przez funkcję `_sektor()` (np. `"Struktura FF"` → `"FF"`). Jeśli `arkusz` jest pusty (pracownik zaimportowany tylko z KOMPETENCJE), `sektor = ''`.

Widok `wyniki_przydzialu` uzupełnia brakujący `sektor` z bazy przy renderowaniu (backwards-compat dla starych przydziałów).

### 6.8 Struktura JSON `PrzydzialDzienny.dane`

Klucze zewnętrzne: `"0"` (pracownicy "bez zmiany" bez żadnego dopasowania — tylko
`__fillers__`, patrz 6.3), `"1"`/`"2"`/`"3"` (zmiany I–III), `"4"` (zmiana D, obecna tylko
jeśli istnieje choć jeden pasujący pracownik), opcjonalnie `"__ostrzezenia_dzialow__"`
(lista stringów — ostrzeżenia fuzzy-matchingu P2 w strefie niepewności [0.70, 0.85), patrz
6.4). Obiekty przydzielonych pracowników mają trzy nowe pola audytowe: `dzial_ok`,
`fuzzy_score`, `kompetencja_uzyta` (patrz 6.4) — fillerzy ich nie mają, bo nie zostali
kosztowani jako przydzieleni.

```json
{
  "1": {
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
          "wynik": 4.2,
          "zapychacz": false,
          "apt": false,
          "dzial_ok": true,
          "fuzzy_score": 1.0,
          "kompetencja_uzyta": 4.2
        }
      ],
      "godziny": {"6": 3.0, "7": 5.0, "8": 5.0, "9": 4.0}
    },
    "__fillers__": {
      "nazwa": "(bez przypisanej aktywności)",
      "dzial": "",
      "wymagana": 12,
      "pracownicy": [
        {
          "pk": 99,
          "imie": "Anna",
          "nazwisko": "Nowak",
          "zmiana_grupa": "A-2",
          "nieobecny": false,
          "powod": "capacity",
          "sektor": "FF",
          "wynik": null,
          "zapychacz": true,
          "apt": false
        }
      ],
      "powody": {"nieobecny": 3, "capacity": 7, "no_match": 2},
      "godziny": {}
    }
  },
  "2": { "...": "..." },
  "3": { "...": "..." },
  "4": { "...": "..." },
  "0": { "__fillers__": { "...": "..." } },
  "__ostrzezenia_dzialow__": [
    "Dział pracownika 'Dzial Kompletacji' vs dział aktywności 'kompletacja': podobieństwo 0.71 — wymaga ręcznej weryfikacji."
  ]
}
```

---

## 7. Macierz procesowa i fuzzy-matching

### 7.1 `grupy_procesowe.py`

Plik `apps/pracownicy/grupy_procesowe.py` zawiera stałą `GRUPY_PROCESOWE: list[dict]` — 57 grup procesowych, 158 czynności. Każda grupa:

```python
{
    "nr": 9,
    "nazwa": "Batch Mezz > szt > (Sort/PTS/PTL) [Inbound]",
    "czynnosci": [
        "RETAIL Batch Mezz > szt > (Sort/PTS/PTL) P0/P1",
        "SPL STOCK Batch Mezz > szt > (Sort/PTS/PTL) P0/P1",
    ]
}
```

### 7.2 Funkcje module-level (views.py)

| Symbol | Opis |
|---|---|
| `_GP` | Alias `GRUPY_PROCESOWE` |
| `_GP_BY_NR` | `{nr: grupa}` dla szybkiego lookup |
| `_akt_to_group_exact` | `{czynnosc_nazwa: grupa}` — exact match lookup |
| `_MANUAL_MAP` | `{_nrm(nazwa): [nr, ...]}` — ręczne mapowania dla niepasowalnych nazw |
| `_nrm(s)` | Normalizacja: lowercase + collapse whitespace + usuń spację przed `)` lub `]` |
| `_words(s)` | `_nrm` + usuń interpunkcję + filtr słów ≥ 3 znaki |
| `_find_all_groups(nazwa)` | Fuzzy-match nazwy aktywności → lista grup |
| `_sektor(arkusz)` | Wyciąga skrót sektora z nazwy arkusza: `"Struktura FF"` → `"FF"` |

### 7.3 Łańcuch dopasowań `_find_all_groups`

1. **Exact** — `_akt_to_group_exact.get(akt_nazwa)`
2. **Substring nazwy grupy** (min 3 znaki)
3. **Word-set nazwy grupy** (min 2 słowa)
4. **Substring czynności** (min 4 znaki)
5. **Word-set czynności** (min 2 słowa)
6. **`_MANUAL_MAP`** — ręczne mapowania dla znanych literówek i agregatów

**Wynik:** 75/78 aktywności planu dopasowanych (96%). Bez grupy: `SKU do przyjęcia`, `Struktura`, `Suma do Przyjęcia`.

### 7.4 Widok macierzy procesowej (`/pracownicy/macierz-procesowa/`)

Tryby (`?tryb=`):
- `mapowanie` (domyślny) — tabela: aktywność DB × grupy procesowe
- `ranking` — ranking pracowników per grupa procesowa

---

## 8. System modali — wyniki_przydzialu.html

| Trigger | Data | Zawartość modalu |
|---|---|---|
| `.akt-modal-trigger` | `data-akt-nazwa` | Grupy procesowe + czynności + pracownicy z oceną |
| `.dzial-modal-trigger` | `data-dzial-nazwa` | Wszystkie grupy procesowe działu |
| `.prac-modal-trigger` | `data-prac-pk` | Top 4 kompetencje + ranking grup procesowych |

Dane JSON osadzone w szablonie przez filtr `json_script` (bezpieczny — escapeuje `<`, `>`, `&`):

```html
{{ modal_data|json_script:"modal-data-json" }}
```

W JS czytane przez:

```js
const MODAL_DATA = JSON.parse(document.getElementById('modal-data-json').textContent);
```

Widok przekazuje surowe struktury Pythona (`modal_data`, `worker_data`, `dzial_data`) — nie JSON string. Nie używaj `|safe` dla tych danych.

**APT workers** wyświetlani z `background-color:#fefce8` (inline). Bootstrap `bg-warning-subtle` nie jest używany — w trybie ciemnym renderuje jako ciemnobrązowy.

---

## 9. Routing URL

```
/                                               → redirect do /konta/dashboard/
/admin/                                         → panel administracyjny Django

/konta/login/                                   → logowanie (rate-limited: axes)
/konta/logout/                                  → wylogowanie
/konta/dashboard/                               → przekierowanie po roli

/pracownicy/                                    → lista pracowników             [login]
/pracownicy/<pk>/usun/                          → usuń pracownika (POST)        [admin]
/pracownicy/usun-wszystkich/                    → usuń wszystkich (POST)        [admin]
/pracownicy/<pk>/kompetencje/                   → kompetencje pracownika (AJAX) [login]
/pracownicy/apt/                                → lista pracowników APT         [login]
/pracownicy/plany/                              → lista planów dziennych        [login]
/pracownicy/plany/<pk>/usun/                    → usuń plan (POST)              [admin]
/pracownicy/plany/<pk>/przydziel/               → uruchom przydział (POST)      [login]
/pracownicy/plany/<pk>/wyniki/                  → wyniki przydziału (GET)       [login]
/pracownicy/macierz-procesowa/                  → macierz procesowa             [login]

/import/plan-zmianowy/                          → import planu zmianowego       [login]
/import/pracownicy/                             → import pracowników            [login]
/import/pracownicy-apt/                         → import pracowników APT        [login]

/stanowiska/                                    → lista stanowisk               [login]
/stanowiska/<pk>/                               → podgląd stanowiska            [login]
/stanowiska/dodaj/                              → dodaj stanowisko              [login]
/stanowiska/<pk>/edytuj/                        → edytuj stanowisko             [login]
/stanowiska/<pk>/usun/                          → usuń stanowisko (POST)        [login]

/przydzialy/                                    → dashboard obsady (legacy)     [login]
/przydzialy/historia/                           → historia przydziałów (legacy) [login]

/raporty/obsada/excel/                          → raport Excel                  [login]
```

Legenda: `[login]` = wymaga zalogowania, `[admin]` = wymaga roli `admin` (403 dla innych ról).

**Namespace `pracownicy`** — URL-e `/pracownicy/*`
**Namespace `import_danych`** — URL-e `/import/*`

---

## 10. Konfiguracja i zmienne środowiskowe

Wszystkie zmienne czytane są wyłącznie przez `django-environ` (`env(...)`). Brak hardkodowanych fallbacków dla wartości wrażliwych. Szablon w `.env.example`.

| Zmienna | Wymagana | Opis |
|---|---|---|
| `SECRET_KEY` | Tak | Klucz Django (min. 50 znaków, losowy) |
| `DEBUG` | Tak | `True` (dev) / `False` (prod) |
| `ALLOWED_HOSTS` | Tak | Lista hostów oddzielona przecinkami |
| `DATABASE_URL` | Tak | URL bazy: `sqlite:///db.sqlite3` lub `postgres://user:pass@host/db` |
| `FIELD_ENCRYPTION_KEY` | Tak | Klucz Fernet (base64) dla `django-encrypted-model-fields` |
| `MAX_IMPORT_FILE_SIZE_MB` | Nie | Limit rozmiaru pliku importu Excel (domyślnie `10`) |
| `PRZYDZIAL_PENALTY_DZIAL` | Nie | Kara P2 za niezgodny dział, silnik przydziału (domyślnie `10000`) |
| `PRZYDZIAL_KOSZT_MAX_KOMPETENCJI` | Nie | Maksymalny koszt P3 wynikający z kompetencji (domyślnie `10`) |
| `PRZYDZIAL_BRAK_KOMPETENCJI_PENALTY` | Nie | Dodatkowa kara gdy brak wpisu kompetencji (domyślnie `1`) |

**Ustawienia produkcyjne** (aktywne tylko gdy `DEBUG=False`):

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000      # 1 rok
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

> **Uwaga HSTS:** Po pierwszym wdrożeniu z `HSTS_PRELOAD = True` domena jest blokowana w przeglądarkach na 1 rok. Upewnij się, że SSL działa poprawnie przed wdrożeniem.

---

## 11. Bezpieczeństwo

### 11.1 Kontrola dostępu per-rola

`apps/konta/decorators.py` dostarcza decoratory dla function-based views:

| Decorator | Dozwolone role |
|---|---|
| `@wymaga_roli('admin')` | tylko `admin` |
| `@wymaga_roli('admin', 'hr')` | `admin` lub `hr` (dowolna kombinacja) |
| `@tylko_hr` | `hr`, `admin` |
| `@tylko_kierownik` | `kierownik`, `admin` |
| `@hr_lub_kierownik` | wszystkie trzy role |

**Zachowanie:** niezalogowany → redirect na `/konta/login/`; zalogowany z złą rolą → HTTP 403 (strona `konta/brak_dostepu.html`), nie redirect.

**Widoki wymagające roli `admin`:** `usun_pracownika`, `usun_wszystkich`, `usun_plan`.

Testy kontroli dostępu: `apps/konta/tests.py` — 10 przypadków pokrywających admin/hr/kierownik/anonimowy dla każdego z trzech widoków destrukcyjnych.

---

### 11.2 Rate limiting logowania — django-axes

Konfiguracja w `settings.py`:

```python
AXES_FAILURE_LIMIT = 5          # blokada po 5 nieudanych próbach
AXES_COOLOFF_TIME = 0.25        # 15 minut (wartość w godzinach)
AXES_RESET_ON_SUCCESS = True    # odblokuj przy pomyślnym logowaniu
AXES_LOCKOUT_TEMPLATE = 'konta/zablokowany.html'
```

Zablokowany IP/user widzi stronę `konta/zablokowany.html`. Odblokowanie ręczne: `python manage.py axes_reset` lub przez panel admina (`Axes > Access Attempts`).

Middleware `axes.middleware.AxesMiddleware` musi być ostatnim w `MIDDLEWARE`. Backend `axes.backends.AxesStandaloneBackend` musi być **pierwszy** w `AUTHENTICATION_BACKENDS`.

---

### 11.3 XSS — osadzanie JSON w szablonach

Dane modali (`modal_data`, `worker_data`, `dzial_data`) przekazywane jako surowe struktury Pythona i osadzane przez filtr `json_script` (Django autoescapuje `<`, `>`, `&`). Nie używaj `|safe` dla tych danych.

---

### 11.4 Walidacja plików importu

`apps/pracownicy/validators.py` — funkcja `waliduj_plik_importu(plik)`:

- Rozszerzenie musi być `.xlsx` (case-insensitive)
- Rozmiar ≤ `MAX_IMPORT_FILE_SIZE_MB` MB (domyślnie 10)
- Rzuca `django.core.exceptions.ValidationError` z czytelnym komunikatem
- Stosowana we wszystkich trzech widokach importu

---

### 11.5 Katalog `tmp/`

`tmp/*.json` przechowuje tymczasowe dane podglądu importu (krok upload→podgląd→zatwierdź). Katalog:

- **Nie jest** w `STATICFILES_DIRS` ani serwowany żadnym URL-em
- Nie jest dostępny publicznie przez WhiteNoise
- Pliki kasowane po zatwierdzeniu (`tmp_path.unlink(missing_ok=True)`)

**Management command czyszczący stare pliki:**

```bash
python manage.py cleanup_tmp_imports            # kasuje pliki starsze niż 24h
python manage.py cleanup_tmp_imports --hours 48 # kasuje starsze niż 48h
python manage.py cleanup_tmp_imports --dry-run  # podgląd bez kasowania
```

Rekomendowany cron (codziennie o 3:00):

```
0 3 * * * /sciezka/do/venv/bin/python /sciezka/do/magazyn/manage.py cleanup_tmp_imports
```

---

## 12. Uruchomienie projektu (dev)

```bash
# Aktywacja venv (Windows, PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python manage.py migrate          # w tym migracje axes (axes.0001–0010)
python manage.py createsuperuser
python manage.py runserver
```

Aplikacja: `http://127.0.0.1:8000/`

---

## 13. Format plików do importu

### 13.1 Plan dzienny — `Plan_dzienny_NEW.xlsx`

| Kolumna | Indeks (0-based) | Zawartość |
|---|---|---|
| A | 0 | Nazwa aktywności |
| B | 1 | `'Bufor'` — wiersz nagłówka działu |
| C | 2 | Wolumen |
| L–S | 11–18 | Zmiana I, godziny 6–13 |
| W–AD | 22–29 | Zmiana II, godziny 14–21 |
| AH–AO | 33–40 | Zmiana III, godziny 22–23, 0–5 |

---

### 13.2 Macierz kompetencji — `KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx`

- Kolumna 0: `departament` (np. `FF`, `IN`, `OB.`, `APT 1`)
- Kolumna 11: `zmiana_grupa`
- Kolumny 14+: aktywności, wartość = ocena (tylko > 0 zapisywana)
- Pomijane: kolumny z `'prasa'` w nazwie działu

---

### 13.3 Struktura i absencje — `Struktura___Grafik___Absencje_NEW.xlsx`

- Arkusze: `Struktura IB`, `Struktura OB`, `Struktura FF`, `Struktura PR`, `Struktura ZW`
- Wiersz 6 = nagłówki, wiersz 7+ = dane pracowników
- Kolumny z datą `DD.MM.YYYY` w nagłówku → `AbsencjaPracownika`
- Nazwa arkusza zapisywana w `Pracownik.arkusz`

---

### 13.4 Pracownicy APT — `PracownicyAPT*.xlsx`

Arkusz `PracownicyAPT01`. Kolumny 2,3,4,5,6,8,9,10,13–18 → oceny dla kolumn APT 1–14.

---

## 14. Znane ograniczenia

| Kwestia | Status |
|---|---|
| Obsada stanowisk w `/stanowiska/` i `/przydzialy/` | Stub (0) — stary model `PlanZmiany` usunięty |
| Raport Excel (`/raporty/obsada/excel/`) | Może wymagać aktualizacji pod nowy schemat |
| 3 aktywności bez grupy procesowej | `SKU do przyjęcia`, `Struktura`, `Suma do Przyjęcia` — metryki agregatowe |
| Absencje dla planów bez `data_planu` | Nie są sprawdzane — flaga `nieobecny` zawsze `False` |
| Zmiana D — brak danych godzinowych z pliku | Aktywności Zmiany D nie mają zapotrzebowania godzinowego w standardowym formacie planu; tabela godzinowa wyświetla się dynamicznie z dostępnych danych |

---

*Dokumentacja zaktualizowana: 2026-08-03 | System Magazynowy v2.5 — silnik przydziału NetworkX min-cost flow*
