from django.core.management.base import BaseCommand
from django.conf import settings

from ollama import Client

class Command(BaseCommand):
    help = 'Call Ollama model with a prompt'

    def add_arguments(self, parser):
        parser.add_argument('prompt', type=str, help='The prompt to send to the model')

    def handle(self, *args, **options):
        client = Client(host=settings.OLLAMA_FULL_HOST)
        response = client.chat(model="gemma3", messages=[{"role": "user", "content": options['prompt']}])
        self.stdout.write(response.message.content)
