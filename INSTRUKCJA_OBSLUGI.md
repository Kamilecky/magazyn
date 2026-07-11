# System Magazynowy — Instrukcja obsługi

## Spis treści

1. [Logowanie i wylogowanie](#1-logowanie-i-wylogowanie)
2. [Nawigacja po systemie](#2-nawigacja-po-systemie)
3. [Lista pracowników](#3-lista-pracowników)
4. [Lista pracowników APT](#4-lista-pracowników-apt)
5. [Plany dzienne](#5-plany-dzienne)
6. [Przydział pracowników do planu](#6-przydział-pracowników-do-planu)
7. [Wyniki przydziału](#7-wyniki-przydziału)
8. [Macierz procesowa](#8-macierz-procesowa)
9. [Import danych](#9-import-danych)
   - [Import planu zmianowego](#91-import-planu-zmianowego)
   - [Import pracowników](#92-import-pracowników)
   - [Import pracowników APT](#93-import-pracowników-apt)
10. [Stanowiska](#10-stanowiska)

---

## 1. Logowanie i wylogowanie

### Logowanie

1. Otwórz przeglądarkę i przejdź pod adres aplikacji (np. `http://127.0.0.1:8000/`).
2. Zostaniesz automatycznie przekierowany na stronę logowania.
3. Wpisz **login** i **hasło**, następnie kliknij **Zaloguj**.

### Wylogowanie

1. Kliknij ikonę użytkownika w prawym górnym rogu.
2. Wybierz **Wyloguj**.

---

## 2. Nawigacja po systemie

Po lewej stronie ekranu znajduje się **boczne menu nawigacyjne**.

| Sekcja | Co zawiera |
|---|---|
| **Pracownicy** | Lista pracowników etatowych, Lista pracowników APT |
| **Plany dzienne** | Lista zaimportowanych planów z przyciskami przydziału |
| **Import danych** | Import planu, Import pracowników, Import pracowników APT |
| **Stanowiska** | Lista stanowisk magazynowych |
| **Przydziały** | Dashboard obsady (legacy), Historia przydziałów |
| **Raporty** | Raport obsady w formacie Excel |

**Zwijanie menu:** kliknij przycisk **Zwiń** u góry — menu zwija się do ikon. Stan jest zapamiętywany między sesjami.

---

## 3. Lista pracowników

**Ścieżka:** Menu → **Pracownicy**

### Co widać w tabeli

Każdy wiersz zawiera:
- **Inicjały** — kolorowe koło
- **Imię i nazwisko**
- **Dział** — badge z nazwą działu
- **Zmiana** i **Zmiana/Grupa** (np. `A-1`, `B-2`, `C-3`)
- **Stanowisko**
- **Kompetencje** — liczba aktywności z oceną > 0; kliknij, aby zobaczyć listę w oknie modalnym

### Wyszukiwanie i filtrowanie

- Pole tekstowe — filtruje po imieniu lub nazwisku na bieżąco
- Rozwijana lista **Dział** — zawęża wyniki do wybranego działu
- Pole wyboru **Tylko nieobecni** — pokazuje pracowników z jakąkolwiek absencją

### Usuwanie

- **Pojedynczy pracownik:** ikona kosza → potwierdź
- **Wszyscy:** przycisk **Wyczyść wszystkich** → potwierdź w oknie dialogowym

> Usunięcie jest trwałe. Dane można przywrócić tylko przez ponowny import.

---

## 4. Lista pracowników APT

**Ścieżka:** Menu → **Pracownicy** → **APT**

Tabela pracowników agencji pracy tymczasowej. Kolumny: nazwisko, imię, agencja, płeć, grupa.

---

## 5. Plany dzienne

**Ścieżka:** Menu → **Plany dzienne**

Widok kafelków wszystkich zaimportowanych planów. Każdy kafelek zawiera:
- Nazwę pliku i datę importu
- Liczbę aktywności i rekordów godzinowych
- Status przydziału (kiedy ostatnio przeliczony)
- Przycisk **Przydziel pracowników** — uruchamia/przelicza przydział
- Przycisk **Wyniki** — otwiera stronę wyników (widoczny gdy przydział istnieje)
- Przycisk **Usuń plan**

### Jak zaimportować nowy plan

Kliknij **Import planu zmianowego** w menu bocznym — patrz sekcja 8.1.

---

## 6. Przydział pracowników do planu

**Ścieżka:** Lista planów → przycisk **Przydziel pracowników**

Po kliknięciu system automatycznie:

1. Wczytuje zapotrzebowanie godzinowe z planu dla każdej aktywności i zmiany
2. Dla każdej zmiany (I/II/III) buduje pulę pracowników na podstawie `zmiana_grupa`:
   - Zmiana I → pracownicy z grupą `A-...`
   - Zmiana II → pracownicy z grupą `B-...`
   - Zmiana III → pracownicy z grupą `C-...`
3. Przydziela pracowników do aktywności w kolejności:
   - Priorytetowi etatowi (działy IN/OB/FF/ZW/PR) pasujący do aktywności
   - Pozostali etatowi pasujący do aktywności
   - Pracownicy APT sortowani wg ocen
4. Priorytetowi bez przypisanej aktywności trafiają do najbliższej pasującej
5. Zapisuje wynik i przekierowuje na stronę wyników

**Uwaga:** przycisk „Przydziel" przelicza od nowa — poprzedni wynik zostaje zastąpiony. Możesz przeliczać wielokrotnie (np. po reimporcie pracowników).

### Dopasowanie pracownika do aktywności

Pracownik jest kierowany do aktywności, jeśli spełnia **co najmniej jeden** warunek:
- Jego **stanowisko** (dokładne) zgadza się z nazwą aktywności
- Jego **dział** zawiera się lub zawiera nazwę działu aktywności
- Jego **kod departamentu** (IN/OB/FF/ZW/PR) pasuje do słów kluczowych działu aktywności
- Ma **kompetencję** (ocena > 0) dla tej aktywności w pliku KOMPETENCJE

---

## 7. Wyniki przydziału

**Ścieżka:** Lista planów → przycisk **Wyniki**

### Podsumowanie (góra strony)

Trzy kafelki — po jednym na zmianę — pokazują łączną liczbę przypisanych pracowników i liczbę bez aktywności (fillers).

### Zakładki zmian

Kliknij zakładkę **Zm. 1 / Zm. 2 / Zm. 3**, aby przełączać między zmianami.

### Karta aktywności

Każda aktywność wyświetlona jest jako karta zawierająca:

- **Nagłówek zielony** — plan obsadzony w pełni (`przydzielono ≥ wymagana`)
- **Nagłówek żółty** — niedobór; ikona ostrzeżenia z informacją ile brakuje
- **Badge** `przydzielono / wymagana` — np. `5 / 7`

**Tabela godzinowa:**

| Wiersz | Znaczenie |
|---|---|
| **Plan** | Wymagana liczba pracowników w danej godzinie (czerwone komórki = niedobór) |
| **Fakt** | Faktyczna obsada (stała = liczba przydzielonych pracowników) |

**Lista pracowników:**

Każdy pracownik pokazany jako karta z:
- Inicjał imienia i nazwisko
- **Kolorowy badge grupy zmiany:** `A-1` (zielony), `B-2` (niebieski), `C-3` (czerwony)
- **Badge APT** (żółty) — dla pracowników agencyjnych
- **Tooltip** (najedź kursorem): pełne imię i nazwisko · grupa zmiany · `N` (jeśli nieobecny w dniu planu) · `APT`

### Sekcja „bez przypisanej aktywności"

Na dole każdej zakładki zmiany: lista pracowników, którym nie znaleziono żadnej pasującej aktywności.

### Modale z informacjami szczegółowymi

Kliknij w dowolny z poniższych elementów, aby otworzyć okno z informacjami:

| Element | Co pokazuje modal |
|---|---|
| **Nazwa aktywności** (z ikoną ↗) | Grupy procesowe, do których należy aktywność + lista czynności z macierzy (✓ zielona = aktywność istnieje w bazie) + pracownicy przydzieleni z oceną procesową |
| **Badge działu** (np. „Inbound") | Wszystkie grupy procesowe przypisane do tego działu |
| **Karta pracownika** | Top 4 kompetencje pracownika + jego pozycja rankingowa w grupach procesowych |

### Przelicz ponownie

Przycisk **Przelicz ponownie** w prawym górnym rogu strony uruchamia przydział od nowa (po potwierdzeniu).

---

## 8. Macierz procesowa

**Ścieżka:** Menu → **Pracownicy** → **Macierz procesowa** (lub `/pracownicy/macierz-procesowa/`)

Macierz mapuje 57 grup procesowych na aktywności w bazie danych i pokazuje oceny pracowników per grupa.

### Tryb: Mapowanie

Domyślny widok (`?tryb=mapowanie`). Tabela aktywności z kolorowymi wskaźnikami:
- **Zielony** — czynnosc z grupy procesowej istnieje w bazie danych
- **Czerwony** — czynnosc z macierzy nie ma odpowiednika w bazie

Służy do weryfikacji, czy nazwy aktywności w plikach KOMPETENCJE zgadzają się z nazwami w macierzy kompetencji PDF.

### Tryb: Ranking

Widok `?tryb=ranking`. Dla każdej grupy procesowej lista pracowników z najwyższą średnią oceną (avg wszystkich czynności grupy). Pokazuje, kto jest najlepszym kandydatem do danego procesu.

System przydziału pracowników automatycznie korzysta z tych rankingów — pracownicy z wysokimi ocenami w danej grupie procesowej są kierowani do odpowiadających aktywności w planie.

---

## 9. Import danych

Każdy import działa dwuetapowo: **wgraj → podejrzyj → zatwierdź**.

---

## 9.1 Import planu zmianowego

**Ścieżka:** Menu → **Import danych** → **Import planu zmianowego**

### Wymagany plik

`Plan_dzienny_NEW.xlsx` — układ kolumn musi być zgodny z szablonem.

### Krok 1 — wgranie i podgląd

1. Kliknij **Wybierz plik** i wskaż plik `Plan_dzienny_NEW.xlsx`.
2. Kliknij **Wgraj i podejrzyj**.
3. Sprawdź tabelę podglądu: aktywność, dział, sumy Zmiana I/II/III, wolumen.

### Krok 2 — zatwierdzenie

1. Kliknij **Zatwierdź i zapisz**.
2. Plan zostaje zapisany i pojawia się na liście planów.

### Częste błędy

| Komunikat | Co zrobić |
|---|---|
| *Plik musi być .xlsx* | Upewnij się, że format pliku to Excel 2007+ |
| *Nie znaleziono żadnych aktywności* | Sprawdź, czy kolumna B zawiera wartość `Bufor` w wierszach działów |
| *Błąd parsowania* | Otwórz plik w Excelu, zapisz ponownie i spróbuj jeszcze raz |

---

## 9.2 Import pracowników

**Ścieżka:** Menu → **Import danych** → **Import pracowników**

### Wymagane pliki

Wgraj jeden lub oba:

| Plik | Co zawiera |
|---|---|
| `KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx` | Lista pracowników, oceny kompetencji dla każdej aktywności, `zmiana_grupa` (kol. L) |
| `Struktura___Grafik___Absencje_NEW.xlsx` | Dane kadrowe (stanowisko, dział, zmiana, przełożony), absencje; `zmiana_grupa` z kolumny „Zmiana grupa" |

> **Każdy import zastępuje całą listę pracowników.** Skasowanie nie może być cofnięte — dane można przywrócić tylko przez ponowny import.

### Jak działa scalanie plików

Gdy wgrasz oba pliki jednocześnie, dane z pliku Struktury **nadpisują** dane z KOMPETENCJE dla tych samych pracowników (dopasowanie po nazwisku + imieniu). Wgranie samego pliku KOMPETENCJE też zapisuje `zmiana_grupa` — z kolumny L tego pliku.

### Krok 1 — wgranie i podgląd

1. Wskaż pliki w odpowiednich polach.
2. Kliknij **Wgraj i podejrzyj**.
3. Sprawdź podgląd: liczba pracowników, wypełnione grupy zmian, liczba kompetencji.

### Krok 2 — zatwierdzenie

1. Kliknij **Zatwierdź — zastąp wszystkich pracowników**.
2. System usunie poprzednią listę i wstawi nową wraz z kompetencjami i absencjami.

### Wskazówki

- Wgraj oba pliki jednocześnie, aby uzyskać pełny profil (kompetencje + dane kadrowe + absencje).
- Po reimporcie **przelicz ponownie** plany, aby wyniki przydziału odzwierciedlały nowe dane.
- Jeśli widzisz pracowników bez grupy zmiany w wynikach przydziału — sprawdź, czy kolumna L (KOMPETENCJE) lub „Zmiana grupa" (Struktura) jest wypełniona w pliku.

---

## 9.3 Import pracowników APT

**Ścieżka:** Menu → **Import danych** → **Import pracowników APT**

### Krok 0 — konfiguracja mapowania kolumn (jednorazowe)

Plik APT zawiera 14 kolumn z ocenami (numery 1–14). Musisz przypisać każdej kolumnie nazwę działu.

1. W sekcji **Mapowanie kolumn APT** wypełnij pola 1–14.
2. Kliknij **Zapisz mapowanie**.

Mapowanie jest zapamiętywane — nie trzeba go ustawiać przy każdym imporcie.

### Krok 1 — wgranie i podgląd

1. Wskaż plik `PracownicyAPT*.xlsx`.
2. Kliknij **Parsuj i podejrzyj**.
3. Sprawdź podgląd: nazwisko, imię, agencja, płeć, grupa, liczba ocen > 0.

### Krok 2 — zatwierdzenie

1. Kliknij **Zatwierdź — zastąp wszystkich pracowników APT**.
2. Poprzedni lista APT jest usuwana i zastępowana nową.

---

## 10. Stanowiska

**Ścieżka:** Menu → **Stanowiska**

Widok kart stanowisk magazynowych. Każda karta zawiera parametry fizyczne (wymagana siła, chodzenie, siedzenie, powtarzalność) i pasek obsady.

> **Uwaga:** liczby obsady są aktualnie niedostępne (stub: 0) — moduł jest w trakcie integracji.

### Zarządzanie stanowiskami

- **Dodaj stanowisko** — formularz z pełnymi parametrami
- **Edytuj** / **Usuń** — ikony przy karcie stanowiska

---

*Instrukcja obsługi — System Magazynowy v2.2 | 2026-07-11*
