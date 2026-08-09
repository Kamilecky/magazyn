"""Silnik przydziału pracowników do aktywności planu — NetworkX min-cost flow.

Hierarchia priorytetów jest leksykograficzna, nie ważona:
  P1 — zgodność zmiany (A/B/C/D): twardy filtr. Pracownik niezgodny ze zmianą
       danego "bucketu" (1/2/3/D) w ogóle nie wchodzi do grafu tej zmiany —
       nie ma krawędzi, więc nie może zostać przydzielony, niezależnie od kosztu.
  P2 — zgodność działu (Pracownik.dzial vs Aktywnosc.dzial, fuzzy): miękki koszt,
       ale PENALTY_DZIAL dominuje nad całym zakresem kosztu kompetencji (P3), więc
       żadna kombinacja ocen kompetencji nie może "przebić" niezgodności działu.
  P3 — ocena kompetencji: różnicuje wyłącznie wśród kandydatów już zgodnych
       w P1 i o tym samym statusie P2.

`rozwiaz_zmiane()` buduje graf przepływu (źródło → pracownicy → aktywności → ujście)
i woła `networkx.max_flow_min_cost`, który maksymalizuje liczbę przydzieleń, a dopiero
wśród rozwiązań maksymalnych minimalizuje koszt — dokładnie odpowiada to zasadzie
"P3 różnicuje tylko pomiędzy już kwalifikującymi się kandydatami".
"""
import logging
from difflib import SequenceMatcher
from typing import Callable, NamedTuple, Optional

import networkx as nx
from django.conf import settings

logger = logging.getLogger(__name__)

# Wartości domyślne — nadpisywalne przez ustawienia Django (patrz config/settings.py)
PENALTY_DZIAL_DOMYSLNY = 10_000
KOSZT_MAX_KOMPETENCJI_DOMYSLNY = 10
BRAK_KOMPETENCJI_PENALTY_DOMYSLNY = 1

# Progi fuzzy-matchingu działów (difflib) — stałe modułowe, nie ustawienia Django
FUZZY_PROG_AKCEPTACJI = 0.85
FUZZY_PROG_OSTRZEZENIA = 0.70

# Skala surowej oceny kompetencji w KompetencjaPracownika.wynik (0–50)
WYNIK_MAX = 50


# Odczytuje stałą z ustawień Django, z fallbackiem — pozwala modułowi działać
# samodzielnie (np. w testach) nawet bez wpisu w config/settings.py
def _ustawienie(nazwa: str, domyslna: int) -> int:
    return getattr(settings, nazwa, domyslna)


# ── P1 — twardy filtr zgodności zmiany ────────────────────────────────────────

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


def apt_pasuje_zmiana(pracownik_apt, litera_zmiany: str) -> bool:
    """P1 dla pracowników APT — jedyne pole to `grupa`."""
    zg = (pracownik_apt.grupa or '').upper()
    # `grupa` musi być niepuste I zaczynać się na właściwą literę zmiany
    return bool(zg) and zg.startswith(litera_zmiany)


# ── P2 — fuzzy dopasowanie działu ─────────────────────────────────────────────

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


def buduj_crosswalk_dzialow(pary: set[tuple[str, str]]) -> tuple[dict, list[str]]:
    """Buduje słownik dopasowań działów RAZ na cały przebieg przydziału (nie per para
    pracownik-aktywność w pętli). `pary` = zbiór (dzial_pracownika, dzial_aktywnosci)
    faktycznie występujących w tym przebiegu.

    Zwraca (crosswalk, ostrzezenia):
      crosswalk[(dzial_p, dzial_a)] = (dopasowano, ratio, metoda)
      ostrzezenia = lista czytelnych komunikatów dla par w strefie niepewności
    """
    crosswalk: dict[tuple[str, str], tuple[bool, float, str]] = {}
    ostrzezenia: list[str] = []
    # Każda para (dzial_p, dzial_a) liczona jest raz, niezależnie od tego ilu
    # pracowników/aktywności współdzieli te same nazwy działów w tym przebiegu —
    # stąd `pary` to zbiór (set), nie lista, i dlaczego wołający buduje je z góry.
    for dzial_p, dzial_a in pary:
        wynik = dzialy_fuzzy_match(dzial_p, dzial_a)
        crosswalk[(dzial_p, dzial_a)] = wynik
        if wynik[2] == 'review':
            # Zbieramy czytelny komunikat od razu, żeby wołający (widok) mógł
            # pokazać ostrzeżenia bez ponownego przeliczania dopasowań
            ostrzezenia.append(
                f"Dział pracownika '{dzial_p}' vs dział aktywności '{dzial_a}': "
                f"podobieństwo {wynik[1]:.2f} — wymaga ręcznej weryfikacji."
            )
    return crosswalk, ostrzezenia


# ── P2 + P3 — koszt krawędzi pracownik→aktywność ──────────────────────────────

# Wynik kosztowania jednej krawędzi pracownik→aktywność — koszt do grafu przepływu
# plus metadane audytowe (dzial_ok/fuzzy_score/kompetencja) zapisywane później
# w PrzydzialDzienny.dane, żeby odróżnić dopasowanie idealne od awaryjnego
class KosztDopasowania(NamedTuple):
    koszt: int
    dzial_ok: bool
    fuzzy_score: float
    kompetencja: float
    brak_danych: bool


def koszt_dopasowania(
    dzial_p: str,
    dzial_a: str,
    wynik: Optional[float],
    crosswalk: dict,
    *,
    dept_kod_ok: bool = False,
    penalty_dzial: Optional[int] = None,
    koszt_max_kompetencji: Optional[int] = None,
    brak_kompetencji_penalty: Optional[int] = None,
) -> KosztDopasowania:
    """Koszt krawędzi pracownik→aktywność (zmiana już zweryfikowana przez pasuje_zmiana
    przed dodaniem krawędzi do grafu — ta funkcja liczy wyłącznie P2+P3).

    `dept_kod_ok`: dodatkowa ścieżka zgodności działu poza fuzzy/substring — zgodność
    kodu departamentu (IN/OB/FF/ZW/PR) ze słowami kluczowymi działu (`_dept_matches_akt`
    w views.py). Zachowuje dotychczasowe przydziały pracowników priorytetowych, których
    pole `dzial` bywa sformułowane inaczej niż nagłówek kolumny planu, mimo że kod
    departamentu logicznie pasuje. Dla pracowników APT (brak pola `dzial`) wołający
    powinien przekazać `dept_kod_ok=True` — dla nich pojęcie "niezgodnego działu" nie
    ma dziś odpowiednika w danych źródłowych, więc kosztuje się ich wyłącznie kompetencją.
    """
    # Parametry z ustawień Django, ale każdy da się nadpisać per-wywołanie (przydatne w testach,
    # patrz KosztDopasowaniaTestCase) — stąd trójwartościowe `is not None`, nie zwykłe `or`
    # (żeby jawne 0 przekazane przez wołającego nie zostało zamienione na wartość domyślną).
    penalty_dzial = (penalty_dzial if penalty_dzial is not None
                      else _ustawienie('PRZYDZIAL_PENALTY_DZIAL', PENALTY_DZIAL_DOMYSLNY))
    koszt_max_kompetencji = (koszt_max_kompetencji if koszt_max_kompetencji is not None
                             else _ustawienie('PRZYDZIAL_KOSZT_MAX_KOMPETENCJI', KOSZT_MAX_KOMPETENCJI_DOMYSLNY))
    brak_kompetencji_penalty = (brak_kompetencji_penalty if brak_kompetencji_penalty is not None
                                else _ustawienie('PRZYDZIAL_BRAK_KOMPETENCJI_PENALTY', BRAK_KOMPETENCJI_PENALTY_DOMYSLNY))

    # --- P2: czy dział pasuje? ---
    # Najpierw sprawdzamy cache (crosswalk budowany raz na cały przebieg); jeśli para
    # nie została w nim policzona z jakiegoś powodu, liczymy fuzzy-match na bieżąco
    # jako zabezpieczenie (nie powinno się zdarzyć, gdy wołający buduje crosswalk poprawnie).
    dopasowano, ratio, _metoda = crosswalk.get((dzial_p, dzial_a), None) or dzialy_fuzzy_match(dzial_p, dzial_a)
    dzial_ok = bool(dopasowano or dept_kod_ok)

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

    return KosztDopasowania(
        koszt=int(koszt),
        dzial_ok=dzial_ok,
        fuzzy_score=ratio,
        kompetencja=kompetencja,
        brak_danych=brak_danych,
    )


# ── Graf przepływu i rozwiązanie ──────────────────────────────────────────────

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
