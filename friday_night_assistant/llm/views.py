from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from ollama import Client

class OllamaQueryView(APIView):
    def post(self, request):
        prompt = request.data.get('prompt')
        if not prompt:
            return Response({'error': 'Prompt required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client(host=settings.OLLAMA_FULL_HOST)
            response = client.chat(model="gemma3", messages=[{"role": "user", "content": prompt}])
            return Response({'response': response.message.content})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
