from django.core.management.base import BaseCommand
from friday_night_assistant.matomo.client import MatomoClient
from friday_night_assistant.plugins import AgentPlugins
import json


class Command(BaseCommand):
    help = 'Test Matomo API connection and methods'

    def add_arguments(self, parser):
        parser.add_argument('--site-id', type=int, default=1)
        parser.add_argument('--method', choices=['visits', 'pageviews', 'top-pages', 'bounce-urls'], default='visits')
        parser.add_argument('--period', default='day')
        parser.add_argument('--date', default='today')
        parser.add_argument('--limit', type=int, default=5)

    def handle(self, *args, **options):
        client = MatomoClient()
        site_id = options['site_id']
        method = options['method']
        period = options['period']
        date = options['date']
        limit = options['limit']

        try:
            if method == 'visits':
                out = client.get_visits(site_id, period, date)
                self.stdout.write(json.dumps(out, indent=2, ensure_ascii=False))
                return

            if method == 'pageviews':
                out = client.get_pageviews(site_id, period, date)
                self.stdout.write(json.dumps(out, indent=2, ensure_ascii=False))
                return

            if method == 'top-pages':
                out = client.get_top_pages(site_id, period, date, limit)
                self.stdout.write(json.dumps(out, indent=2, ensure_ascii=False))
                return

            if method == 'bounce-urls':
                agent = AgentPlugins(client)
                out = agent.get_top_bounce_urls(site_id=site_id, period=period, date=date, limit=limit)
                self.stdout.write(json.dumps(out, indent=2, ensure_ascii=False))
                return

        except Exception as e:
            self.stdout.write(json.dumps({"error": str(e)}, indent=2, ensure_ascii=False))
