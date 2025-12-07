from django.urls import path
from .views import OllamaQueryView

urlpatterns = [
    path('query/', OllamaQueryView.as_view(), name='ollama_query'),
]
