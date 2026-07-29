import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

_DEFAULT_AGE_HOURS = 24


class Command(BaseCommand):
    help = (
        'Usuwa pliki tymczasowe importu (tmp/*.json) starsze niż N godzin. '
        'Domyślnie: 24h. Uruchom przez cron: '
        '0 3 * * * /path/to/venv/bin/python manage.py cleanup_tmp_imports'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=_DEFAULT_AGE_HOURS,
            help=f'Usuń pliki starsze niż N godzin (domyślnie {_DEFAULT_AGE_HOURS}).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Wylistuj pliki do usunięcia bez ich kasowania.',
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        tmp_dir = Path(settings.BASE_DIR) / 'tmp'

        if not tmp_dir.exists():
            self.stdout.write('Katalog tmp/ nie istnieje — nic do zrobienia.')
            return

        cutoff = time.time() - hours * 3600
        removed = skipped = 0

        for f in tmp_dir.glob('*.json'):
            if f.stat().st_mtime < cutoff:
                if dry_run:
                    self.stdout.write(f'[dry-run] usunąłbym: {f.name}')
                else:
                    f.unlink()
                removed += 1
            else:
                skipped += 1

        action = 'Znaleziono (dry-run)' if dry_run else 'Usunięto'
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} {removed} plików starszych niż {hours}h; '
                f'pozostawiono {skipped} świeżych.'
            )
        )
