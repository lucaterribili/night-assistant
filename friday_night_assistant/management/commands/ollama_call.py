from django.core.management.base import BaseCommand
from django.conf import settings

from ollama import Client


class Command(BaseCommand):
    help = 'Call Ollama model with a prompt'

    def add_arguments(self, parser):
        parser.add_argument('prompt', type=str, help='The prompt to send to the model')

    def handle(self, *args, **options):
        client = Client(host=settings.OLLAMA_FULL_HOST)

        # Aggiungi stream=True
        response = client.chat(
            model="gemma3",
            messages=[{"role": "user", "content": options['prompt']}],
            stream=True
        )

        # Itera sui chunk della risposta
        for chunk in response:
            # Scrivi ogni chunk senza andare a capo
            self.stdout.write(chunk['message']['content'], ending='')
            self.stdout.flush()  # Forza l'output immediato

        # Vai a capo alla fine
        self.stdout.write('')