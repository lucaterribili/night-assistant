from django.core.management.base import BaseCommand
import json
import time
from typing import Dict, Any, List, Optional

from friday_night_assistant.plugins import AgentPlugins
from friday_night_assistant.llm.llm import LLM, LLMException
from friday_night_assistant.models.mysql_models.models import AgentMemory


class Command(BaseCommand):
    help = "Loop decisione-esecuzione LLM agente"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent: Optional[AgentPlugins] = None
        self.llm: Optional[LLM] = None
        self.method_dict: Dict[str, Dict[str, Any]] = {}

    # ========== PARAMETER CONVERSION ==========

    def _convert_parameter_types(self, args: Dict[str, Any], method_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Converte i parametri ai tipi corretti basandosi sulla specifica del metodo."""
        converted_args = {}
        parameters_spec = method_spec.get('parameters', {})

        for param_name, param_value in args.items():
            if param_name not in parameters_spec:
                self._log_parameter_warning(param_name, "non trovato nella specifica")
                converted_args[param_name] = param_value
                continue

            param_type = parameters_spec[param_name].get('type', 'str')
            converted_args[param_name] = self._convert_single_parameter(
                param_name, param_value, param_type
            )

        return converted_args

    def _convert_single_parameter(self, param_name: str, param_value: Any, param_type: str) -> Any:
        """Converte un singolo parametro al tipo specificato."""
        try:
            if param_value is None:
                return None
            elif param_type == 'int':
                return int(param_value)
            elif param_type == 'float':
                return float(param_value)
            elif param_type == 'bool':
                return self._convert_to_bool(param_value)
            elif param_type == 'list':
                return self._convert_to_list(param_value)
            elif param_type == 'dict':
                return self._convert_to_dict(param_name, param_value)
            else:
                return str(param_value)

        except (ValueError, TypeError, json.JSONDecodeError) as e:
            self._log_conversion_error(param_name, param_value, param_type, e)
            return param_value

    def _convert_to_bool(self, value: Any) -> bool:
        """Converte un valore a boolean."""
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)

    def _convert_to_list(self, value: Any) -> List:
        """Converte un valore a lista."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [item.strip() for item in value.split(',')]
        elif isinstance(value, list):
            return value
        else:
            return [value]

    def _convert_to_dict(self, param_name: str, value: Any) -> Dict:
        """Converte un valore a dizionario."""
        if isinstance(value, str):
            return json.loads(value)
        elif isinstance(value, dict):
            return value
        else:
            self._log_parameter_warning(param_name, "impossibile convertire a dict")
            return value

    # ========== MEMORY MANAGEMENT ==========

    def _get_previous_memories(self) -> List[Dict[str, Any]]:
        """Recupera le memorie precedenti dal database."""
        return list(AgentMemory.objects.order_by('created_at').values_list('value', flat=True))

    def _format_memory_section(self, memories: List[Dict[str, Any]]) -> str:
        """Formatta le memorie in una stringa leggibile."""
        if not memories:
            return ""

        memory_lines = ["Azioni già eseguite:"]

        for idx, mem in enumerate(memories, 1):
            memory_lines.extend(self._format_single_memory(idx, mem))

        memory_lines.append(
            "\nIn base a queste azioni già eseguite e ai loro risultati, decidi cosa fare adesso."
        )
        return "\n" + "\n".join(memory_lines) + "\n"

    def _format_single_memory(self, idx: int, memory: Dict[str, Any]) -> List[str]:
        """Formatta una singola memoria."""
        action = memory.get('action', 'N/A')
        args = memory.get('args', {})
        reason = memory.get('reason', 'N/A')
        result = memory.get('result')

        lines = [
            f"\n{idx}. Azione: {action}",
            f"   Parametri: {json.dumps(args, ensure_ascii=False)}",
            f"   Motivazione: {reason}"
        ]

        if result is not None:
            result_line = self._format_memory_result(result)
            lines.append(result_line)
        else:
            lines.append("   ⏳ Risultato: In attesa...")

        return lines

    def _format_memory_result(self, result: Any) -> str:
        """Formatta il risultato di una memoria."""
        if isinstance(result, dict) and result.get('error'):
            return f"   ❌ Risultato: ERRORE - {result['error']}"
        else:
            return f"   ✓ Risultato ottenuto: {json.dumps(result, ensure_ascii=False, default=str)}"

    def _save_decision_to_memory(self, decision: Dict[str, Any]) -> AgentMemory:
        """Salva una decisione nella memoria dell'agente."""
        return AgentMemory.objects.create(value=decision)

    def _update_memory_with_result(self, memory_record: AgentMemory, result: Any) -> None:
        """Aggiorna un record di memoria con il risultato dell'esecuzione."""
        updated_value = memory_record.value.copy()
        updated_value['result'] = result
        memory_record.value = updated_value
        memory_record.save()

    # ========== PROMPT BUILDING ==========

    def _build_prompt(self, methods: List[Dict], state: Any, memory_section: str) -> str:
        """Costruisce il prompt per l'LLM."""
        prompt_base = """Sei un assistente che gestisce un sistema di contenuti web. I siti nel sistema hanno id 1, 2 e 3.
        
        I contenuti dei siti sono di tipo blog e tutorial.

Hai questi metodi disponibili:
{methods}

Stato corrente:
{state}"""

        if memory_section:
            prompt_base += "\n{memory}"

        prompt_base += """

Decidi quale metodo chiamare e con quali parametri.
Rispondi SOLO con JSON in questo formato:
{{
  "action": "nome_metodo",
  "args": {{parametri}},
  "reason": "perché hai scelto questo",
  "stop": false
}}
Se vuoi fermarti, imposta "stop": true
"""

        return prompt_base.format(
            methods=json.dumps(methods, ensure_ascii=False, indent=2),
            state=json.dumps(state, ensure_ascii=False, indent=2),
            memory=memory_section
        )

    # ========== LLM INTERACTION ==========

    def _get_llm_decision(self, prompt: str) -> Dict[str, Any]:
        """Ottiene una decisione dall'LLM."""
        self._log_prompt(prompt)
        self.stdout.write(self.style.NOTICE('Chiedo a LLM di decidere...'))

        decision = self.llm.generate_json(prompt, timeout=180)

        if not isinstance(decision, dict):
            raise LLMException("Decisione non è dict")

        return decision

    def _handle_llm_error(self, prompt: str, error: LLMException) -> None:
        """Gestisce un errore dell'LLM tentando una risposta raw."""
        self.stdout.write(self.style.ERROR(f'\n✗ Errore LLM: {error}'))
        try:
            raw = self.llm.generate(prompt, json_mode=False, timeout=180)
            self.stdout.write(self.style.WARNING('Risposta raw:'))
            self.stdout.write(raw)
        except Exception as e2:
            self.stdout.write(self.style.ERROR(f'Fallito anche raw: {e2}'))

    # ========== ACTION EXECUTION ==========

    def _execute_action(
            self,
            action: str,
            args: Dict[str, Any],
            memory_record: AgentMemory
    ) -> Any:
        """Esegue un'azione e gestisce il risultato."""
        if action not in self.method_dict:
            error_state = {"error": f"Metodo {action} non trovato"}
            self.stdout.write(self.style.ERROR(f'Metodo {action} non trovato'))
            self._update_memory_with_result(memory_record, error_state)
            return error_state

        try:
            state = self._execute_method(action, args)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Output metodo: {json.dumps(state, ensure_ascii=False, default=str)}'
                )
            )
            self._update_memory_with_result(memory_record, state)
            return state

        except Exception as e:
            error_state = {"error": str(e)}
            self._log_execution_error(action, e)
            self._update_memory_with_result(memory_record, error_state)
            return error_state

    def _execute_method(self, action: str, args: Dict[str, Any]) -> Any:
        """Esegue un metodo specifico con i parametri convertiti."""
        method_spec = self.method_dict[action]
        converted_args = self._convert_parameter_types(args, method_spec)

        self._log_converted_args(converted_args)

        # Debug Matomo se necessario
        if action == 'get_top_bounce_urls':
            self._debug_matomo_call(converted_args)

        return getattr(self.agent, action)(**converted_args)

    # ========== DEBUG ==========

    def _debug_matomo_call(self, converted_args: Dict[str, Any]) -> None:
        """Effettua una chiamata di debug a Matomo per diagnostica."""
        self.stdout.write(self.style.NOTICE('DEBUG - Chiamata diretta a Matomo per debug...'))
        try:
            raw_response = self.agent.matomo.get_top_pages(
                converted_args['site_id'],
                converted_args.get('period', 'day'),
                converted_args.get('date', 'today'),
                converted_args.get('limit', 5) * 2
            )

            self._log_matomo_debug_info(raw_response)

        except Exception as debug_e:
            self._log_matomo_debug_error(debug_e)

    def _log_matomo_debug_info(self, raw_response: Any) -> None:
        """Logga informazioni di debug sulla risposta Matomo."""
        self.stdout.write(
            self.style.NOTICE(f'DEBUG - Risposta raw Matomo tipo: {type(raw_response).__name__}')
        )
        self.stdout.write(
            self.style.NOTICE(
                f'DEBUG - Risposta raw Matomo: '
                f'{json.dumps(raw_response, ensure_ascii=False, indent=2, default=str)}'
            )
        )

        if isinstance(raw_response, dict):
            self._log_dict_debug_info(raw_response)
        elif isinstance(raw_response, list):
            self._log_list_debug_info(raw_response)

    def _log_dict_debug_info(self, response: Dict) -> None:
        """Logga informazioni di debug per una risposta dizionario."""
        self.stdout.write(self.style.NOTICE(f'DEBUG - Keys del dict: {list(response.keys())}'))
        if 'result' in response:
            self.stdout.write(self.style.NOTICE(f'DEBUG - Campo "result": {response["result"]}'))
        values = list(response.values())
        self.stdout.write(self.style.NOTICE(f'DEBUG - Values del dict (primi 3): {values[:3]}'))
        self.stdout.write(
            self.style.NOTICE(f'DEBUG - Tipi values: {[type(v).__name__ for v in values[:3]]}')
        )

    def _log_list_debug_info(self, response: List) -> None:
        """Logga informazioni di debug per una risposta lista."""
        self.stdout.write(self.style.NOTICE(f'DEBUG - Lista con {len(response)} elementi'))
        if response:
            self.stdout.write(
                self.style.NOTICE(f'DEBUG - Primo elemento tipo: {type(response[0]).__name__}')
            )
            self.stdout.write(self.style.NOTICE(f'DEBUG - Primo elemento: {response[0]}'))

    def _log_matomo_debug_error(self, error: Exception) -> None:
        """Logga errori di debug Matomo."""
        import traceback
        self.stdout.write(self.style.ERROR(f'DEBUG - Errore chiamata Matomo: {error}'))
        self.stdout.write(self.style.ERROR(traceback.format_exc()))

    # ========== LOGGING ==========

    def _log_prompt(self, prompt: str) -> None:
        """Logga il prompt inviato all'LLM."""
        self.stdout.write(self.style.MIGRATE_HEADING('\n' + '=' * 80))
        self.stdout.write(self.style.MIGRATE_HEADING('PROMPT INVIATO AL LLM:'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 80))
        self.stdout.write(prompt)
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 80 + '\n'))

    def _log_decision(self, action: str, args: Dict[str, Any], reason: str) -> None:
        """Logga la decisione presa dall'LLM."""
        self.stdout.write(self.style.WARNING(f'\nMetodo scelto: {action}'))
        self.stdout.write(
            self.style.WARNING(f'Parametri: {json.dumps(args, ensure_ascii=False)}')
        )
        self.stdout.write(self.style.WARNING(f'Motivazione: {reason}'))

    def _log_converted_args(self, converted_args: Dict[str, Any]) -> None:
        """Logga gli argomenti convertiti."""
        self.stdout.write(self.style.NOTICE(f'DEBUG - Args convertiti: {converted_args}'))
        self.stdout.write(
            self.style.NOTICE(
                f'DEBUG - Tipi: {[(k, type(v).__name__) for k, v in converted_args.items()]}'
            )
        )

    def _log_parameter_warning(self, param_name: str, message: str) -> None:
        """Logga un warning sui parametri."""
        self.stdout.write(
            self.style.WARNING(f'Parametro {param_name} {message}, uso valore originale')
        )

    def _log_conversion_error(
            self,
            param_name: str,
            param_value: Any,
            param_type: str,
            error: Exception
    ) -> None:
        """Logga un errore di conversione."""
        self.stdout.write(
            self.style.WARNING(
                f'Errore conversione {param_name}={param_value} a {param_type}: {error}. '
                f'Uso valore originale'
            )
        )

    def _log_execution_error(self, action: str, error: Exception) -> None:
        """Logga un errore di esecuzione."""
        import traceback
        self.stdout.write(self.style.ERROR(f'Errore eseguendo {action}: {error}'))
        self.stdout.write(self.style.ERROR(traceback.format_exc()))

    # ========== MAIN LOOP ==========

    def _process_decision_loop(self, methods: List[Dict], state: Any) -> None:
        """Processa il loop principale di decisione."""
        while True:
            # Recupera e formatta la memoria
            previous_memories = self._get_previous_memories()
            memory_section = self._format_memory_section(previous_memories)

            # Costruisci il prompt
            prompt = self._build_prompt(methods, state, memory_section)

            try:
                # Ottieni decisione dall'LLM
                decision = self._get_llm_decision(prompt)

                # Controlla se fermarsi
                if decision.get("stop"):
                    self.stdout.write(self.style.SUCCESS('\nLLM ha deciso di fermarsi.'))
                    break

                # Estrai i dettagli della decisione
                action = decision.get('action')
                args = decision.get('args', {})
                reason = decision.get('reason', 'N/A')

                self._log_decision(action, args, reason)

                # Salva la decisione in memoria
                memory_record = self._save_decision_to_memory(decision)

                # Esegui l'azione
                state = self._execute_action(action, args, memory_record)

                time.sleep(1)

            except LLMException as e:
                self._handle_llm_error(prompt, e)
                break

    def handle(self, *args, **options):
        """Entry point del comando."""
        self.stdout.write(self.style.MIGRATE_HEADING('Avvio agente LLM'))

        # Inizializza componenti
        self.agent = AgentPlugins()
        self.llm = LLM()

        # Ottieni metodi disponibili
        methods = self.agent.get_available_methods()
        self.method_dict = {m['name']: m for m in methods}

        # Stato iniziale
        state = None

        # Esegui il loop principale
        self._process_decision_loop(methods, state)

        self.stdout.write(self.style.MIGRATE_HEADING('\nAgente fermo'))