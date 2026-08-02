from django.conf import settings
from django.core.exceptions import ValidationError

# Stała przelicznikowa: 1 MB = 1 048 576 bajtów
_MB = 1024 * 1024


# Waliduje plik importu przed przetworzeniem — sprawdza rozszerzenie i rozmiar
# Wywoływana we wszystkich trzech widokach importu (plan, pracownicy, APT)
def waliduj_plik_importu(plik):
    """Sprawdza rozszerzenie (.xlsx) i rozmiar (MAX_IMPORT_FILE_SIZE_MB z settings)."""
    if plik is None:
        return
    # Akceptujemy wyłącznie pliki Excel .xlsx (nie .xls, .csv, .xlsm itp.)
    if not plik.name.lower().endswith('.xlsx'):
        raise ValidationError(
            f'Nieprawidłowy format pliku „{plik.name}". Wymagany plik .xlsx.'
        )
    # Limit rozmiaru konfigurowalny w .env (domyślnie 10 MB)
    limit_mb = getattr(settings, 'MAX_IMPORT_FILE_SIZE_MB', 10)
    if plik.size > limit_mb * _MB:
        raise ValidationError(
            f'Plik „{plik.name}" jest za duży ({plik.size // _MB} MB). '
            f'Maksymalny rozmiar: {limit_mb} MB.'
        )
