# System Magazynowy — Dokumentacja projektu

## Spis treści

1. [Przegląd systemu](#1-przegląd-systemu)
2. [Stos technologiczny](#2-stos-technologiczny)
3. [Struktura projektu](#3-struktura-projektu)
4. [Baza danych — modele](#4-baza-danych--modele)
5. [Moduły i funkcje](#5-moduły-i-funkcje)
6. [Routing URL](#6-routing-url)
7. [Konfiguracja i zmienne środowiskowe](#7-konfiguracja-i-zmienne-środowiskowe)
8. [Uruchomienie projektu](#8-uruchomienie-projektu)
9. [Format plików do importu](#9-format-plików-do-importu)

---

## 1. Przegląd systemu

System Magazynowy to aplikacja webowa zbudowana w Django 5.2, przeznaczona do zarządzania pracownikami magazynowymi i ich dopasowywaniem do stanowisk pracy według planu zmiany.

**Główny przepływ pracy:**

1. **Import pracowników** — wgraj plik Excel lub CSV z listą pracowników i ich doświadczeniem; AI (GPT-4o-mini) automatycznie rozpoznaje kolumny
2. **Import planu zmiany** — wgraj plik Excel z wymaganą obsadą stanowisk na zmianę poranną, popołudniową lub nocną; AI wyciąga pary: stanowisko → liczba wymaganych osób
3. **Dopasowanie obsady** — jedno kliknięcie uruchamia algorytm, który przypisuje pracowników z pasującym doświadczeniem do stanowisk z planu, bez podwójnego przypisania
4. **Podgląd wyników** — kafelki planów z listą dopasowanych pracowników (modal po kliknięciu stanowiska), stanowiska z paskami obsady
5. **Eksport PDF** — pobranie planu zmiany jako sformatowany plik PDF z tabelą obsady

Dostęp do wszystkich widoków wymaga zalogowania. Aplikacja działa wyłącznie w przeglądarce.

---

## 2. Stos technologiczny

| Warstwa | Technologia |
|---|---|
| Backend | Django 5.2, Python 3.13 |
| Baza danych | SQLite (dev) |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.11, Vanilla JS |
| AI / Import | OpenAI API — model `gpt-4o-mini` |
| Excel (odczyt) | openpyxl 3.1.5 |
| PDF | reportlab (przez xhtml2pdf) — czcionka Arial z `C:/Windows/Fonts` |
| Szyfrowanie pól | django-encrypted-model-fields 0.6.5 + cryptography |
| Zmienne środowiskowe | django-environ 0.11.2 |
| Serwowanie plików statycznych | WhiteNoise 6.8.2 |

---

## 3. Struktura projektu

```
magazyn/
├── apps/
│   ├── konta/          # Uwierzytelnianie i role użytkowników
│   ├── pracownicy/     # Główny moduł: pracownicy, import, plany zmian, dopasowanie, PDF
│   ├── rekruci/        # Legacy (zachowany w bazie, URL niedostępny)
│   ├── stanowiska/     # Stanowiska magazynowe (PTS 4, PTS 10 itp.)
│   ├── przydzialy/     # Dashboard obsady + historia przydziałów (legacy)
│   ├── scoring/        # Legacy: silnik scoringu AI dla rekrutów
│   └── raporty/        # Eksport Excel (raport obsady)
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── templates/
│   ├── base.html
│   ├── pracownicy/     # lista.html, import.html, plany_lista.html, import_plan_*.html, plan_pdf.html
│   ├── stanowiska/
│   ├── przydzialy/
│   ├── raporty/
│   └── konta/
├── .env
├── requirements.txt
├── manage.py
└── db.sqlite3
```

---

## 4. Baza danych — modele

### 4.1 `pracownicy.Pracownik`

Pracownik zaimportowany z pliku zewnętrznego.

| Pole | Typ | Opis |
|---|---|---|
| `imie` | CharField(100) | Imię pracownika |
| `nazwisko` | CharField(100) | Nazwisko pracownika |
| `doswiadczenie` | JSONField | Lista kwalifikacji/stanowisk, np. `["PTS 4", "Wózek - Retrack"]` |
| `created_at` | DateTimeField | Data importu |
| `updated_at` | DateTimeField | Data ostatniej modyfikacji |

**Brak UniqueConstraint** — dwie osoby o tym samym imieniu i nazwisku to dwa osobne rekordy.

**Logika importu:** każdy import zastępuje całą poprzednią listę (`DELETE` + `bulk_create`). Doświadczenie przepisywane dokładnie z pliku — bez filtrowania.

---

### 4.2 `pracownicy.PlanZmiany`

Plan pracy na zmianę z wymaganiami obsady i wynikami dopasowania.

| Pole | Typ | Opis |
|---|---|---|
| `nazwa_pliku` | CharField(255) | Nazwa wgranego pliku Excel |
| `zmiana` | CharField(15) | `poranny`, `popobudniowy` lub `nocny` |
| `data_importu` | DateTimeField | Czas wgrania pliku |
| `importowany_przez` | FK(User) | Użytkownik, który wgrał plan |
| `dane_raw` | JSONField | AI-wyekstrahowane wymagania: `[{"stanowisko": "PTS 10", "obsada": 7}, ...]` |
| `dopasowanie` | JSONField | Wyniki dopasowania: `{"PTS 10": [{"imie": "Jan", "nazwisko": "Kowalski", "doswiadczenie": [...]}, ...], ...}` |
| `dopasowane_at` | DateTimeField | Czas ostatniego dopasowania (`null` jeśli nie wykonano) |

**Właściwości modelu:**
- `total_obsada` — suma wymaganej obsady ze wszystkich stanowisk
- `total_dopasowanych` — suma dopasowanych pracowników

**Typy zmian:**

| Wartość | Opis | Ikona |
|---|---|---|
| `poranny` | Zmiana 1 (rano) | ☀️ żółte słońce |
| `popobudniowy` | Zmiana 2 (popołudnie) | 🟠 pomarańczowe słońce |
| `nocny` | Zmiana 3 (noc) | 🌙 niebieski księżyc |

---

### 4.3 `stanowiska.Stanowisko`

Fizyczne stanowisko magazynowe z opisem wymagań.

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

### 4.4 `przydzialy.Przydzia` (legacy)

Historyczne przypisania rekrutów do stanowisk. Model zachowany — nie używany aktywnie.

### 4.5 `przydzialy.AuditLog` (legacy)

Dziennik zdarzeń. Model zachowany — nie używany aktywnie.

### 4.6 `konta.Profil`

| Pole | Typ | Opis |
|---|---|---|
| `user` | OneToOne(User) | Django User |
| `rola` | CharField | `admin`, `hr`, `kierownik` |

---

## 5. Moduły i funkcje

### 5.1 Moduł `pracownicy`

#### Lista pracowników (`/pracownicy/`)

Siatka kart zaimportowanych pracowników ("Zaimportowani pracownicy"). Każda karta zawiera:
- **Avatar** — kolorowe koło z inicjałami
- **Imię i nazwisko** + liczba pozycji doświadczenia
- **Odznaki doświadczenia** — każda pozycja z pola `doswiadczenie` jako osobna odznaka
- **Przycisk usunięcia** — usuwa pojedynczego pracownika z potwierdzeniem `confirm()`

**Pasek narzędzi:** wyszukiwanie po imieniu/nazwisku, sortowanie A–Z / Z–A, licznik widocznych kart. Wszystko client-side (bez przeładowania strony).

**Przycisk "Wyczyść wszystkich"** — widoczny tylko gdy lista nie jest pusta. Usuwa wszystkich pracowników po potwierdzeniu w modalu Bootstrap (`backdrop: static`).

---

#### Import pracowników (`/pracownicy/import/`)

Import listy pracowników z pliku Excel (`.xlsx`) lub CSV (`.csv`).

**Proces:**
1. Plik konwertowany do tekstu (wiersze oddzielone `|`)
2. Wysłany do `gpt-4o-mini` z promptem wyciągającym imię, nazwisko i doświadczenie
3. AI zwraca tablicę JSON: `[{"imie": "...", "nazwisko": "...", "doswiadczenie": ["...", "..."]}]`
4. Cała poprzednia lista pracowników jest usuwana (`DELETE ALL`)
5. Nowi pracownicy wstawiani jednym `bulk_create`
6. Komunikat: `Zaimportowano X pracowników (AI wykryło Y wierszy)`

**Uwaga:** AI przepisuje doświadczenie dokładnie tak jak w pliku — brak filtrowania. Wiersz z pustym imieniem lub nazwiskiem jest pomijany (liczony jako `pominieto`).

---

#### Plany stanowiskowe (`/pracownicy/plany/`)

Główny widok planów zmian — kafelki wszystkich zaimportowanych planów.

**Każdy kafelek pokazuje:**
- Ikonę i tytuł: `Plan DD.MM.YYYY poranny / popołudniowy / nocny`
- Badge "Dopasowano" / "Nie dopasowano"
- Odznaki stanowisk z wymaganą obsadą (np. `PTS 10 [7]`) — **klikalne**
- Po kliknięciu odznaki stanowiska: modal z tabelą dopasowanych pracowników (imię, nazwisko, doświadczenie)
- Łączną wymaganą obsadę i liczbę stanowisk
- Liczbę dopasowanych pracowników i datę dopasowania

**Przyciski kafelka:**
- **Dopasuj obsadę** — modal z potwierdzeniem Tak/Nie, po akceptacji uruchamia algorytm automatyczny
- **Edytuj obsadę** (`bi-pencil-square`) — otwiera modal ręcznej edycji (patrz niżej)
- **Zmień typ** (`bi-arrow-repeat`) — cyklicznie przełącza: poranny → popołudniowy → nocny → poranny
- **PDF** (`bi-file-earmark-pdf`) — pobiera plik PDF z tabelą obsady
- **Kosz** — usuwa plan po potwierdzeniu

---

#### Import planów zmian

| URL | Zmiana |
|---|---|
| `/pracownicy/import/plan/poranny/` | Plan poranny (zmiana 1) |
| `/pracownicy/import/plan/popobudniowy/` | Plan popołudniowy (zmiana 2) |
| `/pracownicy/import/plan/nocny/` | Plan nocny (zmiana 3) |

**Proces:**
1. Plik Excel konwertowany do tekstu (wiersze oddzielone `|`)
2. Wysłany do `gpt-4o-mini` z `SYSTEM_PROMPT_PLAN` wyciągającym pary: stanowisko → obsada
3. AI rozpoznaje różne formaty (kolumna obsady lub lista pracowników na stanowiskach — zlicza)
4. Wynik zapisywany jako `PlanZmiany.dane_raw`: `[{"stanowisko": "PTS 10", "obsada": 7}, ...]`
5. Przekierowanie na `/pracownicy/plany/`
6. Komunikat: `Zaimportowano plan poranny: X stanowisk, łączna obsada Y osób`

Podczas przetwarzania wyświetlany jest modal ładowania (Bootstrap, `backdrop: static, keyboard: false`).

---

#### Ręczna edycja dopasowania (`/pracownicy/plany/<pk>/edytuj-dopasowanie/`)

Modal edycji pozwala kierownikowi ręcznie zmienić przypisanie pracowników do stanowisk.

**Działanie modala:**
1. Kliknięcie "Edytuj obsadę" pobiera dane przez `GET /pracownicy/plany/<pk>/dane-edycji/` (spinner podczas ładowania)
2. Modal pokazuje sekcję dla każdego stanowiska z `dane_raw`:
   - Licznik `X/Y` — aktualnie przypisani / wymagana obsada (zielony ≥ Y, pomarańczowy > 0, czerwony = 0)
   - Lista przypisanych pracowników z przyciskiem usunięcia przy każdym
   - Pole wyszukiwania z live dropdown (filtruje po imieniu/nazwisku, max 25 wyników)
   - Pracownicy przypisani do innego stanowiska w tym planie oznaczeni `* przypisany: [stanowisko]` — system **nie blokuje** podwójnego przypisania (świadoma decyzja kierownika)
3. Zmiany są lokalne (JS) do momentu kliknięcia "Zapisz zmiany"
4. Zapis wysyła `POST /pracownicy/plany/<pk>/edytuj-dopasowanie/` z JSON i przeładowuje stronę

**Endpoint GET** `/pracownicy/plany/<pk>/dane-edycji/` zwraca:
```json
{
  "dane_raw": [{"stanowisko": "PTS 10", "obsada": 7}, ...],
  "dopasowanie": {"PTS 10": [{"imie": "Jan", "nazwisko": "Kowalski", "doswiadczenie": [...]}]},
  "wszyscy_pracownicy": [{"imie": "...", "nazwisko": "...", "doswiadczenie": [...]}]
}
```

**Endpoint POST** `/pracownicy/plany/<pk>/edytuj-dopasowanie/` przyjmuje:
```json
{"dopasowanie": {"PTS 10": [{"imie": "Jan", "nazwisko": "Kowalski", "doswiadczenie": [...]}]}}
```
Waliduje że stanowiska istnieją w `dane_raw`, nadpisuje `PlanZmiany.dopasowanie` i `dopasowane_at`. Zwraca `{"status": "ok", "total_dopasowanych": X}`.

---

#### Algorytm dopasowania obsady (`_wykonaj_dopasowanie`)

Wywoływany po kliknięciu "Tak, dopasuj" na kafelku planu:

1. Pobiera wszystkich pracowników z bazy (`Pracownik.objects.all()`)
2. Dla każdego stanowiska z `dane_raw` (w kolejności listy):
   - Szuka wśród jeszcze nieprzypisanych pracowników tych, którzy mają to stanowisko w `doswiadczenie`
   - Przypisuje do limitu `obsada`
   - Przypisanych usuwa z puli dostępnych
3. Zapisuje wynik do `PlanZmiany.dopasowanie` + ustawia `dopasowane_at`
4. W wynikach każdy pracownik ma: `imie`, `nazwisko`, `doswiadczenie` (snapshot z momentu dopasowania)

**Zasada:** jeden pracownik = jedno stanowisko w danym planie.

---

#### Eksport PDF planu (`/pracownicy/plany/<pk>/pdf/`)

Generuje PDF za pomocą `reportlab` (bez WeasyPrint — nie obsługuje Windows bez GTK).

**Zawartość PDF:**
- Nagłówek z typem zmiany i datą
- Metadane (plik, liczba stanowisk, łączna obsada, data dopasowania)
- Tabela: Stanowisko | Obsada | Dopasowani pracownicy | Wynik (`X/Y`)
  - Wynik zielony = komplet, pomarańczowy = częściowy, czerwony = 0
- Stopka z datą generowania i użytkownikiem

**Czcionka:** Arial z `C:/Windows/Fonts/arial.ttf` rejestrowana w reportlab — obsługuje polskie znaki.

---

### 5.2 Moduł `stanowiska`

#### Lista stanowisk (`/stanowiska/`)

Karty wszystkich stanowisk z paskami obsady. Obsada liczona z pola `dopasowanie` najnowszego planu porannego i nocnego (nie z portfolio pracowników).

Kolory paska:
- Zielony: < 70% zapełnienia
- Żółty: 70–90%
- Czerwony: > 90%

#### Podgląd stanowiska (`/stanowiska/<id>/`)

- Parametry fizyczne stanowiska
- Pasek obsady z aktualną liczebnością (z `dopasowanie`)
- Tabela dopasowanych pracowników (imię, nazwisko, zmiana, data dopasowania)
- Gdy brak dopasowania — informacja z podpowiedzią

---

### 5.3 Moduł `przydzialy` (częściowo aktywny)

#### Dashboard obsady (`/przydzialy/`)

Karty aktywnych stanowisk z paskami obsady — obsada z `PlanZmiany.dopasowanie`. Przycisk "Szczegóły" prowadzi do podglądu stanowiska.

#### Historia przydziałów (`/przydzialy/historia/`)

Tabela historycznych przydziałów z modelu legacy `Przydzia`.

---

### 5.4 Moduł `raporty`

#### Raport obsady Excel (`/raporty/obsada/excel/`)

Pobierany plik `.xlsx` z danymi obsady stanowisk.

---

### 5.5 Moduł `konta`

#### Logowanie (`/konta/login/`)

Formularz logowania Django. Po zalogowaniu przekierowanie na `/konta/dashboard/`.

#### Dashboard (`/konta/dashboard/`)

- `admin` → `/admin/`
- inne role → `/pracownicy/`

---

### 5.6 Nawigacja — Sidebar

| Sekcja | Linki |
|---|---|
| **Pracownicy** | Zaimportowani pracownicy, Import (Excel / CSV) |
| **Plany zmian** | Plany stanowiskowe, Import planu porannego, Import planu popołudniowego, Import planu nocnego |
| **Stanowiska** | Lista stanowisk |
| **Przydziały** | Dashboard obsady, Historia przydziałów |
| **Raporty** | Raport obsady (Excel) |
| **Administracja** | Panel admina (tylko rola `admin`) |

**Zachowanie sidebaru:**
- Przycisk "Zwiń" zwija do samych ikon (szerokość 56 px); stan zapisywany w `localStorage`
- Gdy zwinięty: tekst etykiety "Zwiń/Rozwiń" znika, zostaje tylko ikona
- Gdy zwinięty: najechanie kursorem na ikonę linku pokazuje tooltip z nazwą linku (ciemna dymka, JS-driven, pozycjonowana poza `overflow: hidden` sidebaru)

---

## 6. Routing URL

```
/                                               → redirect do /konta/dashboard/
/admin/                                         → panel administracyjny Django

/konta/login/                                   → logowanie
/konta/logout/                                  → wylogowanie
/konta/dashboard/                               → przekierowanie po roli

/pracownicy/                                    → lista pracowników
/pracownicy/import/                             → import pracowników (Excel / CSV)
/pracownicy/<pk>/usun/                          → usuń pracownika (POST)
/pracownicy/usun-wszystkich/                    → usuń wszystkich pracowników (POST)
/pracownicy/plany/                              → lista planów zmian (kafelki)
/pracownicy/plany/<pk>/dopasuj/                 → uruchom dopasowanie obsady (POST)
/pracownicy/plany/<pk>/dane-edycji/             → pobierz dane do edycji (GET, JSON)
/pracownicy/plany/<pk>/edytuj-dopasowanie/      → zapisz ręczne dopasowanie (POST, JSON)
/pracownicy/plany/<pk>/zmien-typ/               → przełącz typ planu poranny↔popołudniowy↔nocny (POST)
/pracownicy/plany/<pk>/pdf/                     → pobierz plan jako PDF (GET)
/pracownicy/plany/<pk>/usun/                    → usuń plan (POST)
/pracownicy/import/plan/poranny/                → import planu porannego
/pracownicy/import/plan/popobudniowy/           → import planu popołudniowego
/pracownicy/import/plan/nocny/                  → import planu nocnego

/stanowiska/                                    → lista stanowisk
/stanowiska/<pk>/                               → podgląd stanowiska

/przydzialy/                                    → dashboard obsady
/przydzialy/historia/                           → historia przydziałów

/raporty/obsada/excel/                          → raport Excel
```

---

## 7. Konfiguracja i zmienne środowiskowe

Plik `.env` w katalogu głównym projektu (nie dodawać do repozytorium):

```env
DEBUG=True
SECRET_KEY=<losowy-klucz-django>
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
FIELD_ENCRYPTION_KEY=<klucz-fernet-base64>
OPENAI_API_KEY=<klucz-api-openai>
```

### Generowanie kluczy

```python
# FIELD_ENCRYPTION_KEY
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())

# SECRET_KEY
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Klucz OpenAI API

Pobierz z [platform.openai.com](https://platform.openai.com) → API Keys. Wymagany do importu pracowników i planów.

---

## 8. Uruchomienie projektu

### Wymagania

- Python 3.10+
- Windows (generowanie PDF korzysta z `C:/Windows/Fonts/arial.ttf`)
- Środowisko wirtualne (`myvenv`)

### Instalacja

```bash
# Aktywacja venv (Windows)
C:\Odzyskane\PythonVSFolder\.vscode\My_Django_Projects\myvenv\Scripts\activate

# Instalacja zależności
pip install -r requirements.txt

# Uzupełnij plik .env (patrz sekcja 7)

# Migracje bazy danych
python manage.py migrate

# Utwórz superużytkownika
python manage.py createsuperuser

# Uruchomienie serwera deweloperskiego
python manage.py runserver
```

Aplikacja dostępna pod: `http://127.0.0.1:8000/`

---

## 9. Format plików do importu

### 9.1 Plik pracowników (Excel `.xlsx` lub CSV `.csv`)

AI rozpoznaje kolumny automatycznie — nazwy i kolejność kolumn są dowolne.

**Wymagane dane:**
- Kolumna z imieniem
- Kolumna z nazwiskiem
- Jedna lub więcej kolumn z doświadczeniem / stanowiskami / kwalifikacjami

**Przykład Excel:**

| Imię | Nazwisko | Doświadczenie 1 | Doświadczenie 2 |
|---|---|---|---|
| Jan | Kowalski | PTS 4 | Wózek - Retrack |
| Anna | Nowak | PTS 10 | |

**Przykład CSV:**
```csv
Imie,Nazwisko,Stanowisko
Jan,Kowalski,PTS 4
Anna,Nowak,PTS 10
```

Każdy import **zastępuje całą poprzednią listę** pracowników.

---

### 9.2 Plik planu zmiany (Excel `.xlsx`)

AI wyciąga pary: stanowisko → wymagana obsada. Obsługiwane formaty arkusza:

**Format 1 — kolumna obsady:**

| Stanowisko | Obsada |
|---|---|
| PTS 10 | 7 |
| PTS 4 | 5 |
| Sorter - Wrzucanie | 3 |

**Format 2 — lista pracowników na stanowiskach (AI zlicza):**

| Imię | Nazwisko | Stanowisko |
|---|---|---|
| Jan | Kowalski | PTS 10 |
| Anna | Nowak | PTS 10 |
| ... | ... | PTS 10 |

AI rozpoznaje też inne układy tabel i nagłówki w dowolnym języku.

---

*Dokumentacja zaktualizowana: 2026-05-31 | System Magazynowy v1.4*
