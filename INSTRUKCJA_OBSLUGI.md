# System Magazynowy — Instrukcja obsługi

## Spis treści

1. [Logowanie i wylogowanie](#1-logowanie-i-wylogowanie)
2. [Nawigacja po systemie](#2-nawigacja-po-systemie)
3. [Lista pracowników](#3-lista-pracowników)
4. [Import pracowników z pliku](#4-import-pracowników-z-pliku)
5. [Stanowiska](#5-stanowiska)

---

## 1. Logowanie i wylogowanie

### Logowanie

1. Otwórz przeglądarkę i przejdź pod adres aplikacji (np. `http://127.0.0.1:8000/`).
2. Zostaniesz automatycznie przekierowany na stronę logowania.
3. Wpisz **login** i **hasło**, następnie kliknij przycisk **Zaloguj**.

Po poprawnym zalogowaniu system przeniesie Cię na listę pracowników.

### Wylogowanie

1. Kliknij ikonę użytkownika w prawym górnym rogu ekranu (lub swoje imię i nazwisko).
2. Z rozwiniętego menu wybierz **Wyloguj** (czerwony przycisk).

---

## 2. Nawigacja po systemie

Po lewej stronie ekranu znajduje się **boczne menu nawigacyjne** (sidebar). Zawiera ono wszystkie dostępne sekcje systemu.

### Sekcje menu

| Sekcja | Co zawiera |
|---|---|
| **Pracownicy** | Lista pracowników, Import z pliku |
| **Stanowiska** | Lista stanowisk magazynowych |
| **Przydziały** | Dashboard obsady, Historia przydziałów |
| **Raporty** | Raport obsady w formacie Excel |

### Zwijanie menu

Menu boczne można zwinąć, aby uzyskać więcej miejsca na ekranie. Kliknij przycisk **Zwiń** u góry menu — menu zwinęło się do samych ikon. Aby je rozwinąć, kliknij ponownie. Stan zwinięcia/rozwinięcia jest zapamiętywany między sesjami.

---

## 3. Lista pracowników

**Ścieżka:** Menu boczne → **Pracownicy** → **Lista pracowników**

### Co widać na liście

Pracownicy wyświetlani są jako karty. Każda karta zawiera:

- **Avatar** — kolorowy okrąg z inicjałami pracownika
- **Imię i nazwisko**
- **Liczba stanowisk** w portfolio pracownika
- **Kafelki stanowisk** — jedno pole na każde stanowisko z portfolio:
  - Nazwa stanowiska
  - Zielony badge **100%** — oznacza, że pracownik zna to stanowisko
  - Zielony pasek wypełniony do końca

Jeśli pracownik nie ma przypisanego żadnego stanowiska, karta zawiera komunikat **"Brak przypisanych stanowisk"**.

### Tooltip — szczegóły stanowiska

Najedź kursorem myszy na kafelek stanowiska — pojawi się ciemna dymka z podstawowym profilem tego stanowiska (poziom dźwigania, chodzenia, siedzenia, powtarzalności i informacja, czy praca odbywa się na zewnątrz). Dymka znika, gdy odsuniesz kursor.

### Wyszukiwanie pracownika

W pasku nad kartami znajduje się pole tekstowe **Szukaj po imieniu lub nazwisku**. Wpisz dowolną część imienia lub nazwiska — karty filtrują się na bieżąco, bez przeładowania strony.

### Filtrowanie po stanowisku

Obok pola wyszukiwania znajduje się lista rozwijana **Stanowisko**. Wybierz konkretne stanowisko (np. *PTS 4*), aby zobaczyć tylko pracowników, którzy mają je w swoim portfolio. Opcja *Wszystkie stanowiska* przywraca pełną listę.

### Sortowanie

Trzecia lista rozwijana pozwala posortować widoczne karty:

- **Alfabetycznie A–Z** — od Adamski do Żurek
- **Alfabetycznie Z–A** — od Żurek do Adamski

Sortowanie działa po nazwisku, a przy tym samym nazwisku — po imieniu.

### Licznik wyników

W prawym rogu paska narzędzi wyświetlana jest aktualna liczba widocznych kart. Liczba zmienia się automatycznie po zastosowaniu filtrów.

---

## 4. Import pracowników z pliku

**Ścieżka:** Menu boczne → **Pracownicy** → **Import (Excel / CSV)**

Import pozwala załadować listę pracowników z zewnętrznego pliku. System używa sztucznej inteligencji (Claude AI), która samodzielnie rozpoznaje kolumny z danymi — nie musisz dostosowywać formatu pliku do żadnego szablonu.

### Obsługiwane formaty plików

- **Excel** — pliki `.xlsx` (Microsoft Excel 2007 i nowsze)
- **CSV** — pliki `.csv` z separatorem przecinka lub średnika, kodowanie UTF-8

### Jak powinien wyglądać plik

Plik powinien zawierać co najmniej trzy rodzaje danych dla każdego pracownika:

- **Imię**
- **Nazwisko**
- **Stanowiska** — nazwy stanowisk, które pracownik potrafi obsługiwać

Kolumny mogą mieć dowolne nazwy (np. *Imię*, *First name*, *Pracownik*) i stać w dowolnej kolejności. AI rozpozna je automatycznie.

**Przykład pliku Excel:**

| Imię | Nazwisko | PTS 4 | PTS 10 | Wózek |
|---|---|---|---|---|
| Jan | Kowalski | TAK | | TAK |
| Anna | Nowak | | TAK | |

**Przykład pliku CSV:**

```
Imie,Nazwisko,Stanowisko
Jan,Kowalski,PTS 4
Anna,Nowak,PTS 10
```

### Obsługiwane nazwy stanowisk

System rozpoznaje następujące stanowiska (AI dopasuje je nawet jeśli w pliku użyto skrótu lub nieco innej pisowni):

- PTS 4
- PTS 10
- Sorter - Wrzucanie
- Sorter - Zbieranie
- AA
- Wózek - Czołówka
- Wózek - Retrack
- Wózek - Piesek

Inne wartości są ignorowane — nie powodują błędu, po prostu nie zostaną zapisane.

### Jak przeprowadzić import — krok po kroku

1. Przejdź do strony **Import (Excel / CSV)**.
2. Kliknij pole **"Wybierz plik"** i wskaż plik `.xlsx` lub `.csv` na swoim komputerze.
3. Kliknij przycisk **Importuj**.
4. Pojawi się okno z animowanym kółkiem ładowania i komunikatem **"Trwa przetwarzanie pliku"**. Poczekaj — nie zamykaj przeglądarki ani nie odświeżaj strony. Czas oczekiwania zależy od liczby wierszy w pliku i wynosi zazwyczaj kilka sekund.
5. Po zakończeniu zostaniesz automatycznie przeniesiony na listę pracowników.
6. Na górze strony pojawi się zielony komunikat potwierdzający, np.:

   > *Dodano: 12, zaktualizowano: 3 pracowników. Pracownicy przypisani do stanowisk: PTS 4 (7 os.), PTS 10 (5 os.), Wózek - Retrack (4 os.).*

### Aktualizacja istniejących pracowników

Jeśli pracownik o tym samym imieniu i nazwisku już istnieje w bazie, jego dane **zostaną zaktualizowane** — system nie stworzy duplikatu. Dotyczy to w szczególności listy stanowisk: nowy import zastępuje poprzednią listę stanowisk dla tego pracownika.

### Co zrobić w przypadku błędu

Jeśli import się nie powiedzie, na stronie pojawi się czerwony komunikat z opisem problemu:

| Komunikat | Co zrobić |
|---|---|
| *Nieprawidłowy format pliku* | Sprawdź, czy plik ma rozszerzenie `.xlsx` lub `.csv` |
| *Błąd odczytu pliku Excel* | Plik może być uszkodzony — spróbuj zapisać go ponownie w Excelu |
| *Błąd API Anthropic* | Problem z połączeniem do AI — skontaktuj się z administratorem |
| *Nie można sparsować odpowiedzi AI jako JSON* | AI zwróciła nieoczekiwaną odpowiedź — spróbuj ponownie |

---

## 5. Stanowiska

**Ścieżka:** Menu boczne → **Stanowiska** → **Lista stanowisk**

### Lista stanowisk

Widok przedstawia karty wszystkich aktywnych stanowisk magazynowych. Każda karta zawiera:

- **Nazwa** stanowiska i jego status (Aktywne / Nieaktywne)
- **Pasek obsady** — pokazuje, ilu pracowników jest przypisanych do stanowiska w stosunku do maksymalnej liczby miejsc
  - Zielony pasek: stanowisko zajęte poniżej 70%
  - Żółty pasek: zajęte w 70–90%
  - Czerwony pasek: zajęte powyżej 90%
- **Tabela parametrów** — wymagana siła, poziom chodzenia, siedzenia, powtarzalność, praca na zewnątrz
- Przycisk **Szczegóły i obsada** prowadzący do widoku szczegółowego

### Szczegóły stanowiska

Po kliknięciu **Szczegóły i obsada** otwiera się widok szczegółowy stanowiska. Zawiera:

**Parametry stanowiska** — pełna lista wymagań fizycznych: wymagana siła, zakres dźwigania, poziom chodzenia, siedzenia, powtarzalność, praca stojąca, monitor, komputer, praca na zewnątrz, maksymalna liczba pracowników.

**Pasek obsady** — aktualny procent zapełnienia stanowiska (liczba pracowników przypisanych do stanowiska / liczba maksymalna).

**Lista pracowników** — tabela z imionami i nazwiskami wszystkich pracowników, którzy mają to stanowisko w swoim portfolio. Kolumny tabeli:
- Numer porządkowy
- Imię i nazwisko
- Inne stanowiska pracownika (jako odznaki)
- Data ostatniej aktualizacji danych pracownika

Jeśli żaden pracownik nie jest przypisany do stanowiska, wyświetlany jest komunikat z podpowiedzią, aby wykonać import pliku.

---

*Instrukcja obsługi — System Magazynowy v1.1 | 2026-05-26*
