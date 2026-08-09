# Decyzje projektowe — silnik przydziału (NetworkX min-cost flow)

Ściąga: pięć pytań, które najczęściej padają o nowy silnik przydziału (`apps/pracownicy/przydzial_flow.py`,
wdrożony 2026-08-03), z uzasadnieniem w prostych słowach i dokładnym wskazaniem, gdzie w kodzie
dana decyzja jest zaimplementowana. Pełny techniczny opis: `DOKUMENTACJA.md`, sekcja 6.

---

## 1. Czemu zmieniłem algorytm

> Stary sposób przydzielania działał tak, że brał pracownika i przypisywał go od razu, krok po
> kroku, bez oglądania się wstecz. Problem był taki, że czasem pierwszy przydział okazywał się
> nietrafiony, bo dwa kroki później pojawiał się ktoś, kto pasował dużo lepiej — ale było już za
> późno, tamten pracownik był już zajęty. Nowe podejście patrzy na całość na raz — bierze
> wszystkich pracowników i wszystkie stanowiska jednocześnie i dopiero wtedy szuka najlepszego
> możliwego układu. Dzięki temu unikamy takich „wpadek”.

**Plik:** `apps/pracownicy/przydzial_flow.py` — funkcja `rozwiaz_zmiane()`

```python
def rozwiaz_zmiane(
    pracownicy_spec: list[dict],
    aktywnosci_spec: list[dict],
    koszt_fn: Callable[[dict, dict], KosztDopasowania],
) -> dict:
    """Buduje graf min-cost-flow dla jednego "bucketu" zmiany i rozwiązuje go.

    `pracownicy_spec`: lista {'key': hashable, ...} — pracownicy już przefiltrowani
        przez P1 (pasuje_zmiana/apt_pasuje_zmiana) PRZED wywołaniem tej funkcji;
        w obrębie jednego bucketu każdy z nich może połączyć się z każdą aktywnością
        (P1 działa na poziomie przynależności do bucketu, nie per para).
    `aktywnosci_spec`: lista {'pk': int, 'capacity': int} — aktywności z pojemnością
        > 0 (aktywności o zerowej/ujemnej pojemności są pomijane).
    `koszt_fn(worker_spec, akt_spec) -> KosztDopasowania`.

    Zwraca {akt_pk: [(worker_key, KosztDopasowania), ...]} — tylko faktycznie
    przydzieleni pracownicy, wynikający z maksymalnego przepływu o minimalnym koszcie
    (nikt nie zostaje nieprzydzielony tylko dlatego, że jest "drogi" — koszt decyduje
    WYŁĄCZNIE o tym, KTO wypełnia dostępne miejsca, nigdy o TYM, ile miejsc się wypełnia).
    """
    # Aktywności bez wolnej pojemności nie mają po co istnieć w grafie — pomijamy je
    # od razu, żeby graf był mniejszy i żeby `wyniki` od razu miało poprawne klucze.
    aktywnosci_spec = [a for a in aktywnosci_spec if a['capacity'] > 0]
    wyniki = {a['pk']: [] for a in aktywnosci_spec}
    if not pracownicy_spec or not aktywnosci_spec:
        return wyniki  # nie ma kogo z kim łączyć — pusty wynik, bez wołania networkx

    # Węzły identyfikowane krotkami ('W', key) / ('A', pk) zamiast gołych identyfikatorów,
    # żeby PK pracownika i PK aktywności nigdy się przypadkiem nie zderzyły w tym samym grafie
    # (oba to liczby całkowite z niezależnych sekwencji autoincrement w bazie).
    G = nx.DiGraph()

    # Krawędź źródło→pracownik, pojemność 1: każdy pracownik może zostać przydzielony
    # do co najwyżej JEDNEJ aktywności w tym bucketcie. Koszt 0 — P1/P2/P3 liczy się
    # wyłącznie na krawędzi pracownik→aktywność, nie tutaj.
    for w in pracownicy_spec:
        G.add_edge('S', ('W', w['key']), capacity=1, weight=0)

    # Krawędź aktywność→ujście, pojemność = liczba wolnych miejsc na tę aktywność.
    for a in aktywnosci_spec:
        G.add_edge(('A', a['pk']), 'T', capacity=int(a['capacity']), weight=0)

    # Krawędzie pracownik→aktywność: KAŻDY pracownik z każdą aktywnością tego bucketu
    # (P1 już zadecydował KTO w ogóle trafił do pracownicy_spec — tu nie filtrujemy
    # nic dalej, tylko kosztujemy P2+P3 przez koszt_fn). edge_meta trzyma metadane
    # (dzial_ok/fuzzy_score/kompetencja) osobno, bo krawędzie grafu niosą tylko liczby.
    edge_meta: dict[tuple, KosztDopasowania] = {}
    for w in pracownicy_spec:
        wnode = ('W', w['key'])
        for a in aktywnosci_spec:
            koszt = koszt_fn(w, a)
            anode = ('A', a['pk'])
            G.add_edge(wnode, anode, capacity=1, weight=int(koszt.koszt))
            edge_meta[(w['key'], a['pk'])] = koszt

    if G.number_of_edges() == 0:
        return wyniki

    # Sedno algorytmu: max_flow_min_cost NAJPIERW maksymalizuje liczbę przydzieleń
    # (tyle, ile fizycznie mieści się w pojemnościach), a DOPIERO wśród rozwiązań
    # o tej maksymalnej liczbie przydzieleń wybiera to o najniższym sumarycznym koszcie.
    # To gwarantuje: koszt (P2/P3) nigdy nie zmniejsza liczby obsadzonych miejsc,
    # decyduje wyłącznie o tym, KTO konkretnie je zajmuje.
    flow = nx.max_flow_min_cost(G, 'S', 'T', capacity='capacity', weight='weight')

    # Dekodowanie: krawędź pracownik→aktywność z przepływem >= 1 (może być tylko 0 albo 1,
    # bo jej pojemność to 1) oznacza faktyczne przydzielenie. Odzyskujemy metadane
    # kosztu z edge_meta, bo `flow` zwraca tylko liczby przepływu, nie nasze obiekty.
    for w in pracownicy_spec:
        wnode = ('W', w['key'])
        for a in aktywnosci_spec:
            anode = ('A', a['pk'])
            if flow.get(wnode, {}).get(anode, 0) >= 1:
                wyniki[a['pk']].append((w['key'], edge_meta[(w['key'], a['pk'])]))
    return wyniki
```

Cały graf (wszyscy pracownicy × wszystkie aktywności danego bucketu zmiany) budowany jest **przed**
podjęciem jakiejkolwiek decyzji — `networkx.max_flow_min_cost` widzi wszystkie możliwe pary
naraz, więc nie ma czegoś takiego jak „za późno, tamten już zajęty”. Stara wersja (usunięta,
tier1/tier2/force-assign w `views.py`) szła aktywność po aktywności, przydzielając zachłannie —
dokładnie ten mechanizm, który mógł „zablokować” lepszego kandydata wcześniejszą, gorszą decyzją.

---

## 2. Czemu kolejność kryteriów, a nie średnia

> Ustawiłem to tak, że zmiana pracownika jest święta — jak ktoś nie ma tej zmiany, to koniec, nie
> ma dyskusji, niezależnie jak dobry by nie był. Dopiero potem liczy się dział, i dopiero na samym
> końcu kompetencje. Czemu nie zrobiłem tego jako jedną wspólną ocenę, uśrednioną? Bo wtedy mogłoby
> się zdarzyć, że super kompetentny pracownik z zupełnie złej zmiany „wygrywa” tylko dlatego, że ma
> wysoki wynik gdzie indziej — a to bez sensu, bo fizycznie nie może tam pracować. Więc to nie jest
> średnia ważona, tylko twarda hierarchia — najpierw jedno musi się zgadzać, dopiero potem patrzymy
> na kolejne.

**Plik:** `apps/pracownicy/przydzial_flow.py` — funkcje `pasuje_zmiana()` (P1, twardy filtr) i
`koszt_dopasowania()` (P2 dominuje nad P3)

```python
def pasuje_zmiana(pracownik, litera_zmiany: str) -> bool:
    """P1: czy pracownik etatowy należy do zmiany `litera_zmiany` (np. 'A').

    Priorytet: pole `zmiana` (dokładne dopasowanie do litery), fallback na
    pierwszą literę `zmiana_grupa` (np. "A-1" pasuje do litery "A").
    """
    z = (pracownik.zmiana or '').upper()          # np. "A" — jawnie ustawiona litera zmiany
    zg = (pracownik.zmiana_grupa or '').upper()   # np. "A-1" — grupa w obrębie zmiany
    # Dokładne dopasowanie pola `zmiana` ALBO grupa zaczynająca się na tę literę.
    # Pracownik bez żadnego z pól (obie strony puste) zawsze zwróci False — to
    # celowe: "bez zmiany" ma osobną, zwolnioną z P1 ścieżkę w _wykonaj_przydzial.
    return z == litera_zmiany or zg.startswith(litera_zmiany)
```

`pasuje_zmiana()` decyduje, czy krawędź pracownik→aktywność **w ogóle powstaje** w grafie (patrz
punkt 1) — pracownik z niepasującą zmianą nie ma żadnej krawędzi do żadnej aktywności tego bucketu,
więc `max_flow_min_cost` fizycznie nie ma jak go tam wsadzić, niezależnie od kompetencji.

```python
    # --- P3: ocena kompetencji, przeskalowana z 0-50 (KompetencjaPracownika.wynik) na 0-koszt_max ---
    brak_danych = wynik is None
    kompetencja = 0.0 if brak_danych else max(0.0, min(float(wynik), WYNIK_MAX))  # zabezpieczenie przed wartością spoza 0-50
    kompetencja_int = round(kompetencja * koszt_max_kompetencji / WYNIK_MAX)
    kompetencja_int = max(0, min(kompetencja_int, koszt_max_kompetencji))  # zaokrąglenie może wyjść poza zakres o 1 — przycinamy

    # Wyższa kompetencja → niższy koszt (chętniej wybierany przez min-cost flow).
    # To jedyny składnik kosztu widoczny dla dzial_ok=True — czysty ranking P3.
    koszt = koszt_max_kompetencji - kompetencja_int
    if brak_danych:
        koszt += brak_kompetencji_penalty  # mała kara za brak danych, wciąż w zakresie P3 (<< PENALTY_DZIAL)
    if not dzial_ok:
        # Kara P2 dominująca: nawet przy najwyższej możliwej kompetencji (kompetencja_int
        # == koszt_max_kompetencji, koszt lokalny = 0) suma i tak wynosi >= penalty_dzial,
        # czyli więcej niż JAKAKOLWIEK kombinacja kosztów przy dzial_ok=True.
        koszt += penalty_dzial
```

Gdyby to była średnia ważona (np. `0.7 * ocena_zmiany + 0.3 * ocena_kompetencji`), zawsze istniałaby
jakaś wystarczająco wysoka kompetencja, która przeważyłaby złą zmianę/dział w sumie. Tutaj kara za
zły dział (`penalty_dzial`, domyślnie 10 000) jest o rzędy wielkości większa niż CAŁY możliwy zakres
kosztu kompetencji (0–10) — więc matematycznie nie da się jej „przebić” żadną kombinacją ocen.

---

## 3. Przykład na żywo

> Wyobraź sobie trzech kandydatów na jedno miejsce. Jeden ma najwyższe kompetencje ze wszystkich,
> ale jest z zupełnie innego działu. Dwóch pozostałych ma słabsze kompetencje, ale pasuje działowo.
> System i tak wybierze kogoś z pasującego działu, mimo gorszych umiejętności — bo dział jest
> ważniejszy niż kompetencja. Ten najlepszy dostałby robotę tylko wtedy, gdyby nie było w ogóle
> innych kandydatów.

**Plik:** `apps/pracownicy/tests.py` — `WykonajPrzydzialTestCase.test_a_zgodny_dzial_wygrywa_mimo_nizszej_kompetencji`
(dokładnie ten scenariusz, jako uruchamialny test — `python manage.py test apps.pracownicy`)

```python
    def test_a_zgodny_dzial_wygrywa_mimo_nizszej_kompetencji(self):
        dobry_dzial = Pracownik.objects.create(
            imie='Ana', nazwisko='Zgodna', dzial='Outbound', departament='ZZ', zmiana='A',
        )
        zly_dzial = Pracownik.objects.create(
            imie='Bea', nazwisko='Niezgodna', dzial='Inbound', departament='ZZ', zmiana='A',
        )
        KompetencjaPracownika.objects.create(pracownik=zly_dzial, aktywnosc=self.akt, wynik=50)
        self._zapotrzebowanie(self.akt, zmiana=1, liczba_osob=1)  # capacity=1 — jedno miejsce

        dane = _wykonaj_przydzial(self.plan)
        przydzieleni = {w['pk'] for w in dane['1'][str(self.akt.pk)]['pracownicy']}
        self.assertEqual(przydzieleni, {dobry_dzial.pk})
```

`zly_dzial` ma maksymalną możliwą kompetencję (`wynik=50`, czyli 50/50) i mimo to przegrywa z
`dobry_dzial`, który nie ma żadnego wpisu kompetencji (czyli liczy się jako najgorszy możliwy wynik)
— bo tylko jedno miejsce (`liczba_osob=1`) i dział decyduje pierwszy. Dokładnie ten sam przykład
liczbowy (z konkretnymi kosztami: Jan=1, Anna=6, Piotr=10000) jest opisany krok po kroku w
`DOKUMENTACJA.md`, sekcja 6.0.

---

## 4. Dopasowywanie nazw działów

> Dane wchodzą z dwóch różnych plików Excela i nazwy działów tam bywają zapisane różnie —
> literówki, skróty, różna wielkość liter. Zrobiłem coś, co automatycznie rozpoznaje, że to
> prawdopodobnie ten sam dział, nawet jeśli nazwa nie jest identyczna, ale tylko jeśli podobieństwo
> jest naprawdę wysokie. A jeśli podobieństwo jest średnie — nie za wysokie, nie za niskie — system
> tego nie ignoruje i nie zgaduje w ciemno, tylko wypisuje ostrzeżenie, że to trzeba sprawdzić
> ręcznie. Czyli system wie, kiedy nie jest pewny, i mówi o tym wprost, zamiast udawać.

**Plik:** `apps/pracownicy/przydzial_flow.py` — funkcja `dzialy_fuzzy_match()`

```python
def dzialy_fuzzy_match(dzial_p: str, dzial_a: str) -> tuple[bool, float, str]:
    """Dopasowanie działu pracownika do działu/nagłówka kolumny aktywności.

    Zwraca (dopasowano, wynik_podobienstwa, metoda):
      'substring' — dopasowanie podciągu w dowolnym kierunku (bezpieczny, szybki przypadek)
      'fuzzy'     — difflib ratio >= progu akceptacji (0.85)
      'review'    — ratio w strefie niepewności [0.70, 0.85) — zalogowane ostrzeżenie,
                    traktowane jako NIEdopasowane (nie ciche zaakceptowanie ani odrzucenie)
      'none'      — brak dopasowania
    """
    a, b = (dzial_p or '').strip().lower(), (dzial_a or '').strip().lower()
    if not a or not b:
        return False, 0.0, 'none'          # brak nazwy po jednej ze stron — nic do porównania
    if a in b or b in a:
        return True, 1.0, 'substring'      # szybki, bezpieczny przypadek: jedna nazwa zawiera drugą
    # Dopiero gdy substring zawiedzie, liczymy podobieństwo znak-po-znaku (difflib) —
    # to jest wolniejsza, "prawdziwa" fuzzy ścieżka, dla literówek/skrótów
    ratio = SequenceMatcher(None, a, b).ratio()
    if ratio >= FUZZY_PROG_AKCEPTACJI:
        return True, ratio, 'fuzzy'        # wystarczająco podobne, akceptujemy automatycznie
    if ratio >= FUZZY_PROG_OSTRZEZENIA:
        # Strefa niepewności: ani na tyle podobne żeby zaufać automatowi, ani na tyle
        # różne żeby uznać za oczywiście inny dział — zgłaszamy do ręcznej weryfikacji
        # zamiast ciche zaakceptować (ryzyko złego przydziału) lub ciche odrzucić
        # (ryzyko utraty prawidłowego dopasowania przez literówkę w danych źródłowych).
        logger.warning(
            "Dopasowanie działu do przeglądu ręcznego: %r vs %r (ratio=%.2f)",
            dzial_p, dzial_a, ratio,
        )
        return False, ratio, 'review'
    return False, ratio, 'none'            # wyraźnie różne działy, brak ostrzeżenia (zbyt daleko by to była literówka)
```

Trzy progi: `ratio >= 0.85` → automatyczna akceptacja („to na pewno ten sam dział”),
`0.70 <= ratio < 0.85` → **strefa niepewności**, `dzial_ok=False` (nie zgaduje na tak), ale
`logger.warning(...)` zapisuje to do logu — a zbiorczo trafia też do `PrzydzialDzienny.dane["__ostrzezenia_dzialow__"]`
(budowane przez `buduj_crosswalk_dzialow()` w tym samym pliku), więc ktoś może to później sprawdzić
ręcznie. Poniżej 0.70 → uznane za po prostu różne działy, bez ostrzeżenia.

---

## 5. Etatowi przed agencyjnymi

> To akurat nie jest decyzja techniczna, tylko coś, co ustaliłem wcześniej z użytkownikiem systemu.
> Mogłem zrobić tak, żeby etatowi i agencyjni konkurowali na równych zasadach — byłoby prościej.
> Ale zdecydowaliśmy, że etatowy pracownik zawsze ma pierwszeństwo, nawet jeśli jest gorzej
> dopasowany niż ktoś z agencji. Więc najpierw system obsadza wszystko etatowymi, a agencyjni
> dostają tylko to, co zostanie.

**Plik:** `apps/pracownicy/views.py` — funkcja `_rozwiaz_bucket()` (zagnieżdżona w `_wykonaj_przydzial`)

```python
    def _rozwiaz_bucket(eligible_etat_pks, eligible_apt_pks, shift_acts):
        """Rozwiązuje jeden bucket zmiany jako DWA kolejne przepływy min-cost:
        etat najpierw (P1/P2/P3), APT wypełnia wyłącznie pozostałą pojemność —
        APT nigdy nie wypiera etatowego pracownika (decyzja świadoma, patrz plan)."""
        activities_spec = [{'pk': akt_pk, 'capacity': cap} for akt_pk, cap, _ in shift_acts]
        # Słownik wynikowy inicjalizowany pustymi listami dla KAŻDEJ aktywności bucketu —
        # nawet tej, która ostatecznie nie dostanie nikogo (musi mieć klucz w wyniku).
        akt_assignments: dict[int, list[dict]] = {akt_pk: [] for akt_pk, _, _ in shift_acts}

        # --- Runda 1: etatowi konkurują między sobą na pełnej pojemności każdej aktywności ---
        etat_spec = [{'key': pk} for pk in eligible_etat_pks]
        etat_wynik = przydzial_flow.rozwiaz_zmiane(etat_spec, activities_spec, _koszt_etat)
        uzyci_etat: set[int] = set()
        for akt_pk in akt_assignments:
            for pk, koszt in etat_wynik.get(akt_pk, []):
                akt_assignments[akt_pk].append(_worker_dict(pk, pk_to_p[pk], koszt, apt=False))
                uzyci_etat.add(pk)

        # --- Runda 2: APT dostaje tylko to, czego etatowi nie zajęli (pojemność resztkowa) ---
        # Osobne, następujące po sobie wywołanie rozwiaz_zmiane — nie jeden wspólny graf —
        # to właśnie gwarantuje "etat zawsze przed APT": APT fizycznie nie widzi capacity,
        # które etatowi już skonsumowali, więc nie może z nimi konkurować o te same miejsca.
        residual_spec = [
            {'pk': akt_pk, 'capacity': cap - len(akt_assignments[akt_pk])}
            for akt_pk, cap, _ in shift_acts
        ]
        apt_spec = [{'key': pk} for pk in eligible_apt_pks]
        apt_wynik = przydzial_flow.rozwiaz_zmiane(apt_spec, residual_spec, _koszt_apt)
        uzyci_apt: set[int] = set()
        for akt_pk in akt_assignments:
            for pk, koszt in apt_wynik.get(akt_pk, []):
                akt_assignments[akt_pk].append(_worker_dict(pk, apt_pk_to_p[pk], koszt, apt=True))
                uzyci_apt.add(pk)
```

Dwa **osobne, kolejne** wywołania `rozwiaz_zmiane()` (nie jeden wspólny graf z etatowymi i APT
razem) — to właśnie to wymusza. APT w drugiej rundzie widzi tylko `residual_spec`, czyli miejsca,
które zostały PO tym jak etatowi już zajęli, ile mogli. Pracownik APT fizycznie nie ma jak
konkurować o miejsce, które etatowy już dostał w rundzie 1, niezależnie od tego jak dobrą miałby
ocenę. Potwierdzone jako świadomy wybór podczas planowania implementacji (alternatywą był jeden
wspólny graf z etatowymi i APT kosztowanymi identycznie — odrzucone).
