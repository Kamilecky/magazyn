from django.conf import settings
from django.core.exceptions import ValidationError

_MB = 1024 * 1024


def waliduj_plik_importu(plik):
    """Sprawdza rozszerzenie (.xlsx) i rozmiar (MAX_IMPORT_FILE_SIZE_MB z settings)."""
    if plik is None:
        return
    if not plik.name.lower().endswith('.xlsx'):
        raise ValidationError(
            f'Nieprawidłowy format pliku „{plik.name}". Wymagany plik .xlsx.'
        )
    limit_mb = getattr(settings, 'MAX_IMPORT_FILE_SIZE_MB', 10)
    if plik.size > limit_mb * _MB:
        raise ValidationError(
            f'Plik „{plik.name}" jest za duży ({plik.size // _MB} MB). '
            f'Maksymalny rozmiar: {limit_mb} MB.'
        )
