"""Django management command for TutorialAgent - specialized tutorial agent."""

from typing import Dict, Any

from friday_night_assistant.management.commands.base_subagent import BaseSubAgent
from friday_night_assistant.plugins.tutorial_plugins import TutorialAgentPlugins


class Command(BaseSubAgent):
    """TutorialAgent - Agente specializzato per la gestione dei tutorial."""

    help = "Esegue il TutorialAgent per gestire operazioni sui tutorial"

    AGENT_TYPE = "tutorial"
    AGENT_NAME = "TutorialAgent"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_plugins = TutorialAgentPlugins()

    def add_arguments(self, parser):
        """Aggiungi argomenti per il comando."""
        parser.add_argument(
            '--slug',
            type=str,
            help='Slug del tutorial da processare'
        )
        parser.add_argument(
            '--task',
            type=str,
            help='Task specifico da eseguire (es: analyze, update, improve, check_structure)'
        )
        parser.add_argument(
            '--clear-memory',
            action='store_true',
            help='Pulisce la memoria del TutorialAgent prima di iniziare'
        )

    def _build_prompt(self, methods, state, memory_section, context):
        """Costruisce un prompt specifico per il TutorialAgent."""
        slug = context.get('slug', 'unknown')
        task = context.get('task', 'general')

        prompt_base = f"""Sei TutorialAgent, un assistente specializzato e AUTONOMO nella gestione e ottimizzazione dei tutorial tecnici.

Ti è stato delegato il lavoro sul tutorial con slug: "{slug}"
Contesto generale del task: {task}

Hai questi metodi disponibili:
{{methods}}

Stato corrente:
{{state}}"""

        if memory_section:
            prompt_base += "\n{memory}"

        prompt_base += """

SEI AUTONOMO: Devi decidere tu quali azioni eseguire.

Il tuo workflow tipico:
1. get_tutorial_details - Ottieni i dettagli del tutorial
2. analyze_tutorial_structure - Analizza la struttura del contenuto
3. check_tutorial_prerequisites - Verifica prerequisiti e setup instructions
4. get_tutorial_categories - Verifica le categorie (opzionale)
5. (Eventualmente) update_tutorial_content - Se necessario migliorare il contenuto

Decidi la sequenza di azioni più appropriata in base allo stato corrente.

Rispondi SOLO con JSON in questo formato:
{{
  "action": "nome_metodo",
  "args": {{parametri}},
  "reason": "perché hai scelto questo",
  "stop": false
}}

Quando hai completato TUTTE le analisi e azioni necessarie, imposta "stop": true per tornare al main agent.
"""

        return prompt_base.format(
            methods=methods,
            state=state,
            memory=memory_section
        )

    def handle(self, *args, **options):
        """Entry point del comando - per compatibilità CLI."""
        # Se chiamato da CLI senza contesto, errore
        self.stdout.write(
            self.style.ERROR('TutorialAgent deve essere chiamato tramite delegate_to_tutorial_agent del main agent')
        )

    def execute(self, slug: str, task: str = 'analyze_and_improve') -> Dict[str, Any]:
        """Esegue il TutorialAgent programmaticamente con slug e task.

        Args:
            slug: Slug del tutorial da processare
            task: Task da eseguire

        Returns:
            Risultato dell'esecuzione
        """
        context = {
            'slug': slug,
            'task': task,
        }

        self.stdout.write(
            self.style.MIGRATE_HEADING(f'\n{"=" * 80}')
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(f'TutorialAgent delegato per slug: {slug}, task: {task}')
        )
        self.stdout.write(
            self.style.MIGRATE_HEADING(f'{"=" * 80}\n')
        )

        # Esegui l'agente
        self.run_agent(context)

        # Recupera l'ultima memoria per il risultato
        from friday_night_assistant.models.mysql_models.models import AgentMemory
        last_memory = AgentMemory.objects.filter(
            agent_type=self.AGENT_TYPE
        ).order_by('-created_at').first()

        if last_memory and last_memory.value:
            return {
                'success': True,
                'agent': self.AGENT_NAME,
                'slug': slug,
                'last_action': last_memory.value
            }

        return {
            'success': True,
            'agent': self.AGENT_NAME,
            'slug': slug,
            'message': 'Completato senza memoria finale'
        }

