from django.core.management.base import BaseCommand
from django.db.models.functions import Random

from friday_night_assistant.models.pg_models.models import Post


class Command(BaseCommand):
    help = "Stampa N post casuali dal DB Postgres (default 2)."

    def add_arguments(self, parser):
        parser.add_argument('n', nargs='?', type=int, default=2, help='Numero di post da estrarre')

    def _title_str(self, t):
        if isinstance(t, dict):
            return t.get('en') or next(iter(t.values()), '')
        return str(t)

    def handle(self, *args, **options):
        n = options['n']
        qs = Post.objects.using('postgres').order_by(Random())[:n]
        if not qs:
            self.stdout.write(self.style.WARNING('Nessun post trovato sul DB postgres.'))
            return
        for p in qs:
            title = self._title_str(p.title)
            self.stdout.write(f"{p.id}\t{title}\t{p.status}\t{p.counter}")

