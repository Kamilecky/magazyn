from django.utils import timezone
from apps.stanowiska.models import Stanowisko


class ScoringEngine:
    def score(self, rekrut):
        stanowiska = Stanowisko.objects.filter(aktywne=True)
        wyniki = []
        for stanowisko in stanowiska:
            wynik = self._ocen(rekrut, stanowisko)
            wyniki.append(wynik)
        wyniki.sort(key=lambda x: x['score'], reverse=True)
        return wyniki

    def _ocen(self, rekrut, stanowisko):
        blokady = []
        ostrzezenia = []

        try:
            orzeczenie = rekrut.orzeczenie
        except Exception:
            orzeczenie = None

        try:
            ankieta = rekrut.ankieta
        except Exception:
            ankieta = None

        if orzeczenie is None:
            ostrzezenia.append('Rekrut nie posiada orzeczenia lekarskiego')
            return {
                'stanowisko': stanowisko,
                'score': 0,
                'blokady': ['Brak orzeczenia lekarskiego – nie można przydzielić stanowiska'],
                'ostrzezenia': ostrzezenia,
            }

        if orzeczenie.status == 'niezdolny':
            blokady.append('Rekrut jest niezdolny do pracy (orzeczenie lekarskie)')

        if stanowisko.praca_stojaca and orzeczenie.zakaz_stania:
            blokady.append('Stanowisko wymaga pracy stojącej – zakaz w orzeczeniu')

        if (orzeczenie.max_dzwiganie_kg is not None and
                stanowisko.wymagana_sila_kg > orzeczenie.max_dzwiganie_kg):
            blokady.append(
                f'Stanowisko wymaga dźwigania {stanowisko.wymagana_sila_kg} kg, '
                f'orzeczenie dopuszcza max {orzeczenie.max_dzwiganie_kg} kg'
            )

        if (stanowisko.praca_przy_monitorze and
                orzeczenie.zakaz_monitora_h is not None and
                orzeczenie.zakaz_monitora_h < 6):
            blokady.append(
                f'Stanowisko wymaga pracy przy monitorze, orzeczenie dopuszcza max '
                f'{orzeczenie.zakaz_monitora_h}h/dzień'
            )

        dni_do_wygasniecia = (orzeczenie.data_waznosci - timezone.now().date()).days
        if 0 <= dni_do_wygasniecia <= 30:
            ostrzezenia.append(
                f'Orzeczenie lekarskie wygasa wkrótce ({orzeczenie.data_waznosci:%d.%m.%Y})'
            )

        if rekrut.wiek > 55 and stanowisko.wymagana_sila_kg > 15:
            ostrzezenia.append('Wiek rekruta powyżej 55 lat przy stanowisku wymagającym dźwigania')

        if blokady:
            return {
                'stanowisko': stanowisko,
                'score': 0,
                'blokady': blokady,
                'ostrzezenia': ostrzezenia,
            }

        if ankieta is None:
            return {
                'stanowisko': stanowisko,
                'score': 0,
                'blokady': ['Brak ankiety fizycznej – nie można obliczyć wyniku'],
                'ostrzezenia': ostrzezenia,
            }

        score = self._oblicz_score(ankieta, stanowisko)
        return {
            'stanowisko': stanowisko,
            'score': min(score, 100),
            'blokady': blokady,
            'ostrzezenia': ostrzezenia,
        }

    def _oblicz_score(self, ankieta, stanowisko):
        score = 0

        # Kondycja fizyczna – maks 40 pkt
        if ankieta.max_dzwiganie_kg >= stanowisko.wymagana_sila_kg:
            score += 20
        if stanowisko.wymagana_sila_kg > 0:
            prop = min(ankieta.max_dzwiganie_kg / stanowisko.wymagana_sila_kg, 1.0)
            score += int(prop * 10)
        else:
            score += 10

        if ankieta.komfort_stania >= 4 and stanowisko.praca_stojaca:
            score += 10
        if ankieta.komfort_stania <= 2 and not stanowisko.praca_stojaca:
            score += 10

        # Doświadczenie i umiejętności – maks 30 pkt
        if stanowisko.wymaga_komputera:
            if ankieta.umiejetnosci_komputerowe >= 2:
                score += 20
            elif ankieta.umiejetnosci_komputerowe == 1:
                score += 8
        else:
            score += 15

        if ankieta.tempo_pracy == 'szybkie':
            score += 10
        elif ankieta.tempo_pracy == 'zrownowazone':
            score += 7
        else:
            score += 5

        # Preferencje środowiska – maks 30 pkt
        if stanowisko.praca_stojaca and ankieta.preferuje_ruch:
            score += 15
        if not stanowisko.praca_stojaca and ankieta.preferuje_stale_miejsce:
            score += 15
        if ankieta.preferuje_samodzielnie:
            score += 15

        return score
