# System Magazynowy — Instrukcja Obsługi

## Spis treści

1. [Pierwsze logowanie](#1-pierwsze-logowanie)
2. [Nawigacja](#2-nawigacja)
3. [Lista pracowników etatowych](#3-lista-pracowników-etatowych)
4. [Lista pracowników APT](#4-lista-pracowników-apt)
5. [Import danych](#5-import-danych)
6. [Plany dzienne i przydział](#6-plany-dzienne-i-przydział)
7. [Wyniki przydziału](#7-wyniki-przydziału)
8. [Stanowiska](#8-stanowiska)
9. [Typowe problemy](#9-typowe-problemy)

---

## 1. Pierwsze logowanie

Wejdź na `http://127.0.0.1:8000/` i zaloguj się danymi administratora. Po zalogowaniu zostaniesz przekierowany do widoku listy pracowników.

---

## 2. Nawigacja

Lewy panel nawigacyjny zawiera sekcje:

| Sekcja | Zawiera |
|---|---|
| **Pracownicy** | Lista etatowców, Lista APT |
| **Plany dzienne** | Historia planów i przydział |
| **Import danych** | Trzy okna importu Excel |
| **Stanowiska** | Katalog stanowisk magazynowych |
| **Przydziały** | Dashboard obsady (stub) |

Sidebar można zwinąć do paska ikon — kliknij strzałkę `«` u dołu panelu. Stan zapamiętywany jest w przeglądarce.

---

## 3. Lista pracowników etatowych

Link: **Zaimportowani pracownicy** w sekcji „Pracownicy".

### Kolumny tabeli

| Kolumna | Opis |
|---|---|
| Nr ewid. | Numer ewidencyjny z pliku KOMPETENCJE |
| Nazwisko / Imię | Pełne dane pracownika |
| **Przynależność** | Badge `Etat` (zielony) lub `APT` (żółty) — wskazuje, czy pracownik jest stałym pracownikiem etatowym czy agencyjnym (na podstawie pola `departament`) |
| Data zatr. | Data zatrudnienia |
| Stanowisko | Stanowisko magazynowe |
| Strefa | Strefa w magazynie |
| Dział | Dział pracownika; najedź, by zobaczyć top 4 kompetencje |
| Zmiana / Gr. zm. | Zmiana (I/II/III/D) i kod grupy zmiany |
| Przełożony | Bezpośredni przełożony |
| Absencje | Zarejestrowane absencje; wyświetlane max 3 + licznik pozostałych |
| Komp. | Liczba kompetencji; kliknij, by zobaczyć pełną listę w oknie modalnym |

### Filtry

**Pole wyszukiwania** — wpisz fragment imienia lub nazwiska; lista odświeża się automatycznie po wpisaniu.

**Zakładki arkuszy** (nad tabelą) — kliknij zakładkę (np. `IB`, `FF`, `OB`), by zobaczyć tylko pracowników z danego arkusza Struktury. Zakładka `Wszyscy` przywraca pełną listę.

**Panel filtrów** — po prawej stronie pola wyszukiwania:
- **Tylko z absencjami** — toggle; włączony pokazuje wyłącznie pracowników z przynajmniej jedną absencją
- **Typ: Etat / APT** — dwa checkboxy:
  - zaznacz **Etat** → pokaż tylko pracowników etatowych (bez agencyjnych)
  - zaznacz **APT** → pokaż tylko pracowników agencyjnych
  - oba lub żaden → wszyscy pracownicy

Filtry można łączyć. Przycisk `× Wyczyść filtr` (pojawia się gdy filtry aktywne) resetuje wszystkie parametry.

**Filtry kolumnowe** — dodatkowy wiersz pod nagłówkami tabeli pozwala zawężać wyniki kolumna po kolumnie.

---

## 4. Lista pracowników APT

Link: **Lista APT** w sekcji „Pracownicy".

Wyświetla pracowników tymczasowych (agencyjnych) zaimportowanych z osobnego pliku APT. Kolumny: nazwisko, imię, agencja, płeć, grupa zmiany.

Filtruj po agencji klikając zakładkę nad tabelą. Pole wyszukiwania działa identycznie jak na liście etatowej.

---

## 5. Import danych

### 5.1 Import planu zmianowego

Link: **Import planu zmianowego** w sekcji „Import danych".

1. Kliknij **Wybierz plik** i wskaż plik `Plan_dzienny_NEW.xlsx`.
2. Kliknij **Wgraj i podejrzyj** — zobaczysz podgląd tabeli z zapotrzebowaniem podzielonym na działy i zmiany.
3. Sprawdź dane (liczby w kolumnach godzinowych).
4. Kliknij **Zatwierdź import** — plan zostanie zapisany i pojawi się na liście planów.

> Jeśli kolumna godzinowa zawiera `#DIV/0!`, system traktuje ją jako 0 i informuje ostrzeżeniem.

---

### 5.2 Import pracowników (etatowych i agencyjnych z Kompetencji)

Link: **Import pracowników** w sekcji „Import danych".

**Obsługiwane pliki (oba opcjonalne, najlepiej obydwa razem):**

| Plik | Zawartość |
|---|---|
| `KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx` | Dane pracowników, departament, grupy zmian, macierz kompetencji + oceny |
| `Struktura___Grafik___Absencje_NEW.xlsx` | Dane kadrowe, grupy zmian, absencje; osobne arkusze per sektor (IB/OB/FF/ZW/PR) |

> **Ważne:** Plik Struktury może zawierać zarówno pracowników etatowych (arkusze `Struktura IN/OB/FF/ZW/PR`) jak i agencyjnych (ci z polem `departament = APT 1/2/3/4`). System rozróżnia ich po tym polu — agencyjni są obsługiwani osobno w algorytmie przydziału.

Przebieg:
1. Wybierz jeden lub oba pliki.
2. Kliknij **Wgraj i podejrzyj** → podgląd z liczbą pracowników, kompetencji, absencji.
3. Kliknij **Zatwierdź** — poprzednia lista pracowników zostanie **całkowicie zastąpiona**.

---

### 5.3 Import pracowników APT

Link: **Import pracowników APT** w sekcji „Import danych".

**Krok 1 — mapowanie kolumn:**
Zanim zaczniesz, przypisz numery kolumn (1–14) pliku APT do nazw działów. Kliknij **Konfiguracja kolumn**, wypełnij formularz i zapisz.

**Krok 2 — import pliku:**
Wskaż plik `PracownicyAPT*.xlsx`, kliknij **Wgraj i podejrzyj**, a następnie **Zatwierdź**. Poprzednia lista APT zostanie zastąpiona.

---

## 6. Plany dzienne i przydział

Link: **Plany dzienne** w sekcji nawigacji.

### Kafelek planu

Każdy zaimportowany plan wyświetlany jest jako kafelek z:
- Nazwą pliku i datą importu
- Datą planu (jeśli rozpoznano z nazwy pliku)
- Liczbą aktywności i rekordów godzinowych
- Statusem przydziału (jeśli był uruchomiony): czas ostatniego przeliczenia

**Przyciski:**
- **Przydziel** (lub **Przelicz ponownie**) — uruchamia algorytm przydziału
- **Wyniki** (widoczny gdy przydział istnieje) — otwiera stronę wyników

### Jak działa przydział

Po kliknięciu **Przydziel** system wykonuje automatyczny przydział pracowników do aktywności. Od wersji z sierpnia 2026 silnik przydziału to matematyczny optymalizator (NetworkX, przepływ o minimalnym koszcie), a nie prosty algorytm krok-po-kroku — ale zasady, którymi się kieruje, są proste i mają ścisłą kolejność ważności:

1. **Wczytuje dane** z bazy: plan, pracownicy, kompetencje, oceny, absencje.

2. **Rozróżnia pracowników:**
   - **Etatowi** — pracownicy stali (departament `FF`, `IN`, `OB`, `ZW`, `PR` lub pusty). Pracownicy z `departament = APT*` są wykluczeni z tej puli.
   - **APT** — pracownicy agencyjni z osobnego importu APT (model `PracownikAPT`)
   - **Nieobecni** — pracownicy z absencją w dniu planu (tylko jeśli plan ma datę)

3. **Trzy zasady w ścisłej kolejności ważności (wyższa zasada zawsze bije niższą):**

   **Zasada 1 — zmiana (A/B/C/D), warunek bezwzględny:**
   Pracownik przypisany do zmiany A może trafić wyłącznie do aktywności zmiany A tego dnia. To nie jest "preferencja" ani "kara" — pracownik z niepasującą zmianą w ogóle nie jest brany pod uwagę dla danej aktywności, więc nigdy nie trafi do złej zmiany, nawet gdyby był jedynym kandydatem.

   **Zasada 2 — zgodność działu:**
   Spośród pracowników z pasującą zmianą, system w pierwszej kolejności wybiera tych, których dział pasuje do działu/nagłówka danej aktywności (dopuszczalne drobne różnice nazewnictwa — literówki, skróty, wielkość liter). Pracownik z niepasującym działem może zostać przydzielony **tylko jako rozwiązanie awaryjne**, gdy brakuje jakiegokolwiek kandydata z właściwego działu na dane miejsce.

   **Zasada 3 — ocena kompetencji:**
   Dopiero pomiędzy pracownikami, którzy przeszli obie powyższe zasady, o kolejności decyduje ocena z macierzy kompetencji — wyższa ocena, większy priorytet. Żadna, nawet najwyższa, ocena kompetencji nie może „przebić" niezgodności działu z Zasady 2.

   **APT zawsze na końcu:** dopiero gdy wszyscy pasujący etatowi pracownicy zostali rozdysponowani na dane miejsca (wg Zasad 1–3), pracownicy APT wypełniają pozostałe wolne miejsca wg swojej oceny. APT nigdy nie zajmuje miejsca etatowemu — nawet jeśli ma wyższą ocenę.

4. **Zmiana D (specjalna):**
   Dotyczy pracowników z grupą zmiany zaczynającą się na `D`. Obejmuje aktywności z działów PRASA i KDR. Przetwarzana osobno po zmianach I–III, wg tych samych trzech zasad.

5. **Pracownicy bez przypisanej zmiany** (nie mają ani `zmiana`, ani `zmiana_grupa`) są zwolnieni z Zasady 1 i mogą wypełnić wolne miejsce w dowolnej zmianie I–III — to świadomy wyjątek, nie błąd.

6. **Nieprzydzieleni** trafiają do sekcji „bez przypisanej aktywności" z wyjaśnieniem powodu (patrz sekcja 7.3).

---

## 7. Wyniki przydziału

Link: **Wyniki** przy danym planie lub `.../<pk>/wyniki/`.

### 7.1 Podsumowanie — kafelki zmian

Na górze strony cztery kafelki (Zmiana I, II, III, D) z liczbą:
- przypisanych pracowników (liczba zielona)
- nieprzypisanych (liczba czerwona, jeśli > 0)

### 7.2 Zakładki zmian

Kliknij zakładkę **Zm. I**, **Zm. II**, **Zm. III** lub **Zm. D**, żeby zobaczyć wyniki dla danej zmiany. Liczba w badge zakładki = suma pracowników przydzielonych + nieprzydzielonych.

### 7.3 Tabela aktywności

Dla każdej aktywności:

**Nagłówek aktywności:**
- Nazwa aktywności i działu
- Ikona ostrzeżenia `⚠` gdy faktyczna obsada < wymaganej
- Badge `przydzielono / wymagana` (czerwony przy niedoborze)

**Tabela godzinowa Plan/Fakt:**
- Wiersz **Plan** = wymagana liczba osób dla każdej godziny (komórki czerwone gdy > obsada)
- Wiersz **Fakt** = faktyczna liczba przydzielonych
- Zakres godzin zależy od zmiany (Zm. I: 6–13, Zm. II: 14–21, Zm. III: 22–5)

**Lista pracowników:**
Każdy pracownik ma:
- Badge z kodem grupy zmiany: A=zielony, B=niebieski, C=czerwony, D=fioletowy
- Badge `APT` (żółty) — jeśli pracownik agencyjny
- Badge `N` — jeśli nieobecny w dniu planu (absencja)
- Tooltip (najedź myszą) z pełnym imieniem, grupą, ewentualną absencją

### 7.4 Sekcja „bez przypisanej aktywności"

Pojawia się gdy dla danej zmiany są pracownicy nieprzydzieleni do żadnej aktywności.

**Legenda powodów** (nad listą): liczniki pokazują ile pracowników ma dany powód:

| Kolor badge | Powód | Znaczenie |
|---|---|---|
| Czerwony `(N)` | Nieobecny | Pracownik ma zarejestrowaną absencję w dniu planu |
| Pomarańczowy | Aktywności pełne | Pracownik pasuje do co najmniej jednej aktywności zmiany, ale wszystkie miejsca są zajęte |
| Szary | Brak dopasowania | Pracownik nie pasuje do żadnej aktywności tej zmiany (inny dział, inne kompetencje) |

**Etatowi** i **APT** wyświetlani w osobnych grupach.

**Skrót sektora** (np. `FF`, `OB`, `IN`) widoczny przy każdym etatowcu jako mały szary chip. Pełna informacja dostępna w tooltipie (najedź myszą).

> Sekcja „aktywności pełne" NIE oznacza błędu algorytmu — to normalne zjawisko, gdy plan wymaga mniej osób niż dostępnych pracowników danej zmiany i działu. Ważne: APT nie może być przyczyną zajęcia miejsca etatowemu.

---

## 8. Stanowiska

Link: **Lista stanowisk**.

Katalog stanowisk magazynowych z parametrami fizycznymi (siła dźwigania, intensywność chodzenia, praca na stojąco itp.). Podgląd listy i szczegółów dostępny dla każdej zalogowanej roli; dodawanie, edycja i usuwanie stanowisk wymaga roli **admin**.

---

## 9. Typowe problemy

### Brak zakładki „Zm. D" lub pusta

Zmiana D dotyczy tylko aktywności z działów PRASA i KDR. Jeśli plan nie zawiera takich aktywności, zakładka będzie pusta. Wymaga też pracowników z grupą zmiany zaczynającą się od litery `D`.

### Liczba absencji nie zgadza się z planem

Absencje sprawdzane są tylko gdy plan ma datę. Jeśli data nie była rozpoznana przy imporcie, pole `data_planu` jest puste — absencje nie będą uwzględniane. Sprawdź datę planu w panelu `/admin/`.

### Pracownicy APT widoczni na liście etatowych

Plik KOMPETENCJE może zawierać pracowników agencyjnych z `departament = APT 1/2/3/4`. Są oni widoczni na liście pracowników z żółtym badge'em `APT` i można ich odfiltrować przez checkbox **APT** w panelu filtrów. W algorytmie przydziału są automatycznie wykluczani z puli etatowych i obsługiwani jako APT.

### Po imporcie zniknęli poprzedni pracownicy

Każdy import pracowników zastępuje **całą** listę. Nie ma mechanizmu scalania. Jeśli chcesz zachować dane z dwóch plików jednocześnie, wgraj oba w ramach jednego importu (pola KOMPETENCJE + Struktura).

### Błąd przy wgrywaniu pliku

Sprawdź, czy plik jest zapisany w formacie `.xlsx` (nie `.xls` ani `.csv`) i czy ma poprawne nagłówki kolumn (w odpowiednich wierszach). Szczegóły formatu w `DOKUMENTACJA.md` sekcja 12.

---

*Instrukcja zaktualizowana: 2026-08-03 | System Magazynowy v2.6*
