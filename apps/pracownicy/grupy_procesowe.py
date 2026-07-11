"""
Mapowanie grup procesowych z Macierzy Kompetencji (PDF) na nazwy aktywności w bazie.
Źródło: Macierz_Kompetencji.xlsx — 57 grup procesowych, 158 czynności.
"""

GRUPY_PROCESOWE: list[dict] = [
    {
        "nr": 1,
        "nazwa": "OTHERS RETAIL Unloading",
        "czynnosci": [
            "RETAIL Przyjęcia kwarantanna",
        ],
    },
    {
        "nr": 2,
        "nazwa": "OTHERS RETAIL Inbound + split",
        "czynnosci": [
            "RETAIL Inbound + split",
            "SPL STOCK Inbound + split",
        ],
    },
    {
        "nr": 3,
        "nazwa": "Receiving O4O",
        "czynnosci": [
            "Receiving O4O SORT",
            "Receiving O4O SORT Zwrot",
            "Receiving O4O NSORT",
            "Receiving O4O NSORT Zwrot",
        ],
    },
    {
        "nr": 4,
        "nazwa": "Rozsortowanie do P6/P7",
        "czynnosci": [
            "Rozsortowanie do P6/P7",
        ],
    },
    {
        "nr": 5,
        "nazwa": "Przyjęcie pustych Totesów",
        "czynnosci": [
            "RETAIL Przyjęcie pustych totes",
        ],
    },
    {
        "nr": 6,
        "nazwa": "Putaway P0/P1 - przyjęcia",
        "czynnosci": [
            "RETAIL Put away Przyjęcia > Mezzanine P0/P1",
            "SPL STOCK Put away Przyjęcia > Mezzanine P0/P1",
        ],
    },
    {
        "nr": 7,
        "nazwa": "Putaway P0/P1 - Zwroty",
        "czynnosci": [
            "RETURNS Put away Przyjęcia > Mezzanine P0/P1",
            "Zwroty Ecom - Put away Przyjęcia > Mezzanine P0/P1",
        ],
    },
    {
        "nr": 8,
        "nazwa": "Kompletacja Shuttle (głównie)",
        "czynnosci": [
            "RETAIL Kompletacja Shuttle (głównie others)",
            "SPL STOCK Kompletacja Shuttle (głównie others)",
        ],
    },
    {
        "nr": 9,
        "nazwa": "Batch Mezz > szt > (Sort/PTS/PTL) [Inbound]",
        "czynnosci": [
            "RETAIL Batch Mezz > szt > (Sort/PTS/PTL) P0/P1",
            "SPL STOCK Batch Mezz > szt > (Sort/PTS/PTL) P0/P1",
        ],
    },
    {
        "nr": 10,
        "nazwa": "Kompletacja Ecom Pick",
        "czynnosci": [
            "SPL STOCK Kompletacja Mezz Pick & Pack P0/P1",
            "RETAIL Kompletacja Mezz Pick & Pack P0/P1",
        ],
    },
    {
        "nr": 11,
        "nazwa": "Konsolidacje + zasilenia [Inbound]",
        "czynnosci": [],
    },
    {
        "nr": 12,
        "nazwa": "Kompletacja RTV [Inbound]",
        "czynnosci": [
            "RETURNS Kompletacja Mezz Pick & Pack P0/P1",
            "Zwroty - Kompletacja Batch MP P0/P1",
        ],
    },
    {
        "nr": 13,
        "nazwa": "Pozostałe prace dodatkowe [Inbound]",
        "czynnosci": [
            "RETAIL VAS ręczny P0/P1",
        ],
    },
    {
        "nr": 14,
        "nazwa": "RETURNS Sortowanie na stołach",
        "czynnosci": [
            "RETURNS Sortowanie na stołach",
        ],
    },
    {
        "nr": 15,
        "nazwa": "RETURNS Kompletacja PTS (PTV)",
        "czynnosci": [
            "RETURNS Kompletacja PTS 01 (PTV)",
        ],
    },
    {
        "nr": 16,
        "nazwa": "Przyjęcie CSE LVL",
        "czynnosci": [
            "RETURNS Przyjęcia case lvl",
        ],
    },
    {
        "nr": 17,
        "nazwa": "RETURNSztuki do przyjęcia",
        "czynnosci": [],
    },
    {
        "nr": 18,
        "nazwa": "RETURNS w drodze",
        "czynnosci": [],
    },
    {
        "nr": 19,
        "nazwa": "RETURNS SZT_VD_DO_PRZYJ",
        "czynnosci": [],
    },
    {
        "nr": 20,
        "nazwa": "Anty VAS",
        "czynnosci": [
            "Anty VAS",
        ],
    },
    {
        "nr": 21,
        "nazwa": "ZWROTY Ecom IN",
        "czynnosci": [
            "Zwroty Przyjecia Ecom 500",
            "Zwroty Przyjecia Ecom 600",
            "Zwroty Przyjecia Ecom 700",
            "Zwroty Przyjecia Ecom 100",
            "PTS O4O ZWROTY",
        ],
    },
    {
        "nr": 22,
        "nazwa": "ZWROTY Ecom OUT",
        "czynnosci": [
            "ZWROTY Ecom OUT",
        ],
    },
    {
        "nr": 23,
        "nazwa": "Uszkodzenia",
        "czynnosci": [
            "ECOM Sortowanie na stołach uszkodzenia",
        ],
    },
    {
        "nr": 24,
        "nazwa": "ZWROTY PRASA",
        "czynnosci": [
            "Zwroty Sztuki Backlog",
            "Zwoty Sztuki na dziś",
            "Zwroty Total Sztuki zrobione dziś",
            "Zwroty Sztuki Dostawa",
            "Zwroty Konsygnata Sztuki zrobione dziś INNE",
            "Zwroty Rozsortowanie Sztuki zrobione dziś INNE",
            "Zwroty Reedycja Sztuki zrobione dziś INNE",
            "Zwroty Reedycja Vas zrobione dziś INNE",
            "Zwroty Wydanie INNE",
        ],
    },
    {
        "nr": 25,
        "nazwa": "Pozostałe prace dodatkowe pozostałe",
        "czynnosci": [
            "RETURNS Put away Racks (PAL IN)",
            "RETURNS Replanishment (PAL IN)",
            "RETURNS SPL Units",
            "RETURNS Put away Racks (PAL OUT)",
            "RETURNS Replanishment (PAL OUT)",
            'RETURNS Put away Przyjęcia > Racks R1/R2/R5 "J"',
            "RETURNS Wysyłka",
        ],
    },
    {
        "nr": 26,
        "nazwa": "Putaway P3/P4/P7 - przyjęcia",
        "czynnosci": [
            "RETAIL Put away Przyjęcia > Mezzanine P3 / P4 / G2",
            "SPL STOCK Put away Przyjęcia > Mezzanine P3 / P4 / G2",
        ],
    },
    {
        "nr": 27,
        "nazwa": "Putaway P3/P4/P7 - Zwroty",
        "czynnosci": [
            "Zwroty Ecom - Put away Przyjęcia > Mezzanine P3 / P4 / G2",
            "RETURNS Put away Przyjęcia > Mezzanine P3 / P4 / G2",
        ],
    },
    {
        "nr": 28,
        "nazwa": "Kompletacja Retail Total",
        "czynnosci": [
            "Retail - Kompletacja FPK SAL_OTHERS",
            "Retail - Kompletacja FPK SAL",
        ],
    },
    {
        "nr": 29,
        "nazwa": "Kompletacja Racks Pick & Pack (spożywka + gabaryty) / R1/R2",
        "czynnosci": [
            "RETAIL Kompletacja Racks Pick & Pack R1",
            "RETAIL Kompletacja Racks Pick & Pack R2/R5",
            "RETURNS Kompletacja Racks Pick & Pack R1",
            "RETURNS Kompletacja Racks Pick & Pack R2/R5",
            "SPL STOCK Kompletacja Racks Pick & Pack R1",
            "SPL STOCK Kompletacja Racks Pick & Pack R2",
            "SPL STOCK Kompletacja Racks Pick & Pack R5",
        ],
    },
    {
        "nr": 30,
        "nazwa": "Kompletacja Aapick",
        "czynnosci": [
            "RETAIL Kompletacja AA Pick",
            "RETAIL Kompletacja Racks Pick & Pack R3",
            "RETURNS Kompletacja AA Pick R7/R8",
            "RETURNS Kompletacja Racks Pick & Pack R3",
            "SPL STOCK Kompletacja Racks Pick & Pack R3",
            "SPL STOCK Kompletacja Racks Pick & Pack R7/R8",
        ],
    },
    {
        "nr": 31,
        "nazwa": "Kompletacja Pick & Pack",
        "czynnosci": [
            "RETAIL Kompletacja Mezz Pick & Pack P3 / P4 / G2",
            "RETURNS Kompletacja Mezz Pick & Pack P3 / P4 / G2",
            "SPL STOCK Kompletacja Mezz Pick & Pack P3 / P4 / G2",
        ],
    },
    {
        "nr": 32,
        "nazwa": "Kompletacja Sorter",
        "czynnosci": [
            "RETAIL Kompletacja PTS 02",
            "RETAIL Kompletacja Sorter",
            "RETURNS Kompletacja Sorter",
        ],
    },
    {
        "nr": 33,
        "nazwa": "Kompletacja PTS 03",
        "czynnosci": [
            "RETAIL Kompletacja PTS 03",
            "RETAIL Kompletacja PTS 03 BIS",
        ],
    },
    {
        "nr": 34,
        "nazwa": "Kompletacja PTS 04 BIS",
        "czynnosci": [
            "RETAIL Kompletacja PTS 04 BIS2",
            "RETAIL Kompletacja PTS 04 BIS",
        ],
    },
    {
        "nr": 35,
        "nazwa": "Kompletacja PTS 04 (BTS)",
        "czynnosci": [
            "RETAIL Kompletacja PTS 04",
        ],
    },
    {
        "nr": 36,
        "nazwa": "Kompletacja PTS 06",
        "czynnosci": [
            "RETAIL Kompletacja PTS 06",
        ],
    },
    {
        "nr": 37,
        "nazwa": "Kompletacja PTS 08",
        "czynnosci": [
            "RETAIL Kompletacja PTS 08",
        ],
    },
    {
        "nr": 38,
        "nazwa": "Batch Mezz P3/P4/P7",
        "czynnosci": [
            "RETAIL Batch Mezz > szt > (Sort/PTS/PTL) P3 / P4 / G2",
            "Zwroty - Kompletacja Batch MP P3 / P4 / G2",
            "SPL STOCK Batch Mezz > szt > (Sort/PTS/PTL) P3 / P4 / G2",
        ],
    },
    {
        "nr": 39,
        "nazwa": "Batch Rack > Full paleta > (Sort/PTS/PTL) FPK",
        "czynnosci": [
            "RETAIL Batch Rack > Full paleta > (Sort/PTS/PTL) FPK R1/R2/R5",
            "RETAIL Batch Rack > Full paleta > (Sort/PTS/PTL) FPK R3",
        ],
    },
    {
        "nr": 40,
        "nazwa": "Batch Rack aktywne > szt > (Sort/PTS/PTL)",
        "czynnosci": [
            "RETAIL Batch Rack aktywne > szt > (Sort/PTS/PTL) R1",
            "RETAIL Batch Rack aktywne > szt > (Sort/PTS/PTL) R2/R5",
            "Zwroty - Kompletacja Batch MP R1",
            "Zwroty - Kompletacja Batch MP R2/R5",
            "SPL STOCK Batch Rack aktywne > szt > (Sort/PTS/PTL) R1",
            "SPL STOCK Batch Rack aktywne > szt > (Sort/PTS/PTL) R2/R5",
            "RETAIL Batch Rack aktywne > szt > (Sort/PTS/PTL) R3",
            "RETAIL Batch Rack aktywne > szt > (Sort/PTS/PTL) R7",
            "Zwroty - Kompletacja Batch MP R3",
            "SPL STOCK Batch Rack aktywne > szt > (Sort/PTS/PTL) R3",
            "SPL STOCK Batch Rack aktywne > szt > (Sort/PTS/PTL) R7/R8",
        ],
    },
    {
        "nr": 41,
        "nazwa": "VAS [Fulfilment]",
        "czynnosci": [
            "RETAIL VAS ręczny R1/R2/R5",
            "RETAIL VAS ręczny PTS 02",
            "RETAIL VAS aplikator",
            "RETAIL VAS ręczny R3",
            "RETAIL VAS ręczny P3/P4/G2/R5",
        ],
    },
    {
        "nr": 42,
        "nazwa": "RTV [Fulfilment]",
        "czynnosci": [],
    },
    {
        "nr": 43,
        "nazwa": "Ecom Pick",
        "czynnosci": [
            "ECOM - Kompletacja Batch ECOM PRS",
        ],
    },
    {
        "nr": 44,
        "nazwa": "PTS10",
        "czynnosci": [
            "No Packing PTS 10 Units",
        ],
    },
    {
        "nr": 45,
        "nazwa": "MOP - PTM",
        "czynnosci": [
            "OTH3 Sorting PTM",
        ],
    },
    {
        "nr": 46,
        "nazwa": "MOP - Sorter",
        "czynnosci": [
            "Sorter - Infeed",
        ],
    },
    {
        "nr": 47,
        "nazwa": "Operator RT",
        "czynnosci": [
            "Operator RT",
        ],
    },
    {
        "nr": 48,
        "nazwa": "Konsolidacja + zasilenie Aapick",
        "czynnosci": [
            "RETAIL Put away Przyjęcia > AA Pick R7/R8",
            "RETAIL Replanishment Rack > FPK pal (część palety np. 80%) > Sort/PTS/PTL R3",
            "RETAIL Replanishment Rack > Mezz szt > Put away (końcówka FPK, MIN-MAX) R3",
            "RETAIL Replanishment Rack > Rack aktywne szt R3",
            "SPL STOCK Replanishment Rack > FPK pal (część palety np. 80%) > Sort/PTS/PTL R3",
        ],
    },
    {
        "nr": 49,
        "nazwa": "Konsolidacje + zasilenia (P3/P4/P7)/R1/R2",
        "czynnosci": [
            "RETAIL Replanishment Rack > FPK pal (część palety np. 80%) > Sort/PTS/PTL R1/R2/R5",
            "RETAIL Replanishment Rack > Mezz szt > Put away (końcówka FPK, MIN-MAX) R1/R2/R5",
            "RETAIL Replanishment Rack > Rack aktywne szt R1/R2/R5",
            "SPL STOCK Replanishment Rack > FPK pal (część palety np. 80%) > Sort/PTS/PTL R1/R2/R5",
        ],
    },
    {
        "nr": 50,
        "nazwa": "Wsparcie działu S.C.",
        "czynnosci": [
            "Wsparcie działu S.C.",
        ],
    },
    {
        "nr": 51,
        "nazwa": "Prace Dodatkowe [Fulfilment]",
        "czynnosci": [
            "RETURNS Put away Przyjęcia > Sorter",
            "RETAIL Put away Przyjęcia > Racks rezerwa R1/R2/R5",
            "RETAIL Put away WHSE > Racks R1/R2/R5",
            "RETURNS Put away Przyjęcia > Racks R1/R2/R5",
            "SPL STOCK Put away Przyjęcia > Racks rezerwa R1/R2/R5",
            "Zwroty Ecom - Put away Przyjęcia > Racks R1/R2/R5",
            "RETAIL - PutAway PRS",
            "RETAIL Put away Przyjęcia > Racks rezerwa R3",
            "RETAIL Put away WHSE > Racks R3",
            "RETURNS Put away Przyjęcia > Racks R3",
            "SPL STOCK Put away Przyjęcia > Racks rezerwa R3",
            "Zwroty Ecom - Put away Przyjęcia > Racks rezerwa R3",
        ],
    },
    {
        "nr": 52,
        "nazwa": "E-com total RBH [Outbound]",
        "czynnosci": [
            "Putaway GAB Units",
            "Collecting GAB Units",
            "Putaway P6/P7 Units",
            "Collecting P6/P7 Units",
            "No Packing Pick & Pack P6 Units",
            "Packing GAB Multi Package",
            "Packing GAB Single Package",
            "Packing Multi P6/P7 Package",
            "OTH3 packing single Package",
            "OTH3 packing multi Package",
            "OTH3 putaway multi Units",
        ],
    },
    {
        "nr": 53,
        "nazwa": "Wysyłka E-com",
        "czynnosci": [
            "ECOM Przypisanie do Marshalline",
            "Sorting & marshaling salon Units Stores",
            "Sorting & marshaling salon Package Stores",
            "Sorting & marshaling salon Units Post/Courier",
            "Sorting & marshaling salon Package Post/Courier",
            "Loading Units",
            "FOTO",
            "Audyt paczek salon",
        ],
    },
    {
        "nr": 54,
        "nazwa": "Wysyłka Retail",
        "czynnosci": [
            "RETAIL Przypisanie do Marshalline",
            "RETAIL Wysyłka",
        ],
    },
    {
        "nr": 55,
        "nazwa": "Prace dodatkowe standard [Outbound]",
        "czynnosci": [
            "Prace dodatkowe standard",
        ],
    },
    {
        "nr": 56,
        "nazwa": "E-com total RBH [KDR + Uzupełnienia]",
        "czynnosci": [
            "KDR Sztuki na dziś",
            "KDR Sztuki zrobione na czas",
            "KDR Total sztuki zrobione dziś",
            "KDR Putaway Total sztuki zrobione dziś INNE",
            "KDR Paletyzacja Total sztuki zrobione dziś INNE",
            "Uzupełnienia Sztuki Backlog",
            "Uzupełnienia Sztuki na dziś",
            "Uzupełnienia Sztuki zrobione na czas",
            "Uzupełnienia Total Sztuki zrobione dziś",
            "Uzupełnienia Putaway Total Sztuki zrobione dziś INNE",
            "Uzupełnienia Putaway Zwroty Total Sztuki zrobione dziś INNE",
            "Uzupełnienia RTV Total Sztuki zrobione dziś INNE",
        ],
    },
    {
        "nr": 57,
        "nazwa": "Prace dodatkowe standard [KDR + Uzupełnienia]",
        "czynnosci": [
            "Prace Dodatkowe",
        ],
    },
]
