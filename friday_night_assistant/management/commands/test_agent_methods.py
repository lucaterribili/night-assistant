from django.core.management.base import BaseCommand
from typing import Any, Dict, Optional
import json
import logging

from friday_night_assistant.plugins import AgentPlugins
from friday_night_assistant.plugins.tutorial_plugins import TutorialAgentPlugins
from friday_night_assistant.plugins.post_plugins import PostAgentPlugins

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test helper per eseguire i metodi esposti dai plugin (AgentPlugins, TutorialAgentPlugins, PostAgentPlugins)"

    def add_arguments(self, parser):
        parser.add_argument('--plugin', type=str, choices=['agent', 'tutorial', 'post'], default='agent', help='Plugin da utilizzare: agent, tutorial o post')
        parser.add_argument('--list', action='store_true', help='Elenca i metodi disponibili e la loro specifica')
        parser.add_argument('--method', type=str, help='Nome del metodo da eseguire')
        parser.add_argument('--args-json', dest='args_json', type=str, help='Argomenti JSON (es: "{\"site_id\":1}")')
        parser.add_argument('--auto-run', action='store_true', help='Esegue tutti i metodi con valori di default')
        parser.add_argument('--dry-run', action='store_true', help='Simula l\'esecuzione senza chiamare i metodi')

    def _parse_args_json(self, args_str: Optional[str]) -> Dict[str, Any]:
        """Parse JSON arguments with error handling."""
        if not args_str:
            return {}
        try:
            return json.loads(args_str)
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Errore parsing JSON: {e}'))
            return {}

    def _get_default_value(self, name: str, spec: Dict[str, Any]) -> Any:
        """Get default value for a parameter based on its specification."""
        if 'default' in spec:
            return spec['default']

        ptype = spec.get('type', 'str')
        defaults = {
            'int': 1 if name == 'site_id' else 0,
            'bool': False,
            'list': [],
            'dict': {},
        }
        return defaults.get(ptype, 'sample-slug')

    def _convert_parameter(self, value: Any, param_type: str) -> Any:
        """Convert a single parameter to its expected type."""
        if value is None:
            return None

        converters = {
            'int': lambda v: int(v),
            'float': lambda v: float(v),
            'bool': lambda v: v.lower() in ('true', '1', 'yes') if isinstance(v, str) else bool(v),
            'list': self._convert_to_list,
            'dict': lambda v: json.loads(v) if isinstance(v, str) else v,
        }

        converter = converters.get(param_type, str)
        return converter(value)

    def _convert_to_list(self, value: Any) -> list:
        """Convert value to list with multiple strategies."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [item.strip() for item in value.split(',')]
        return [value]

    def _convert_parameters(self, args: Dict[str, Any], method_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Convert all parameters to their expected types."""
        converted = {}
        params_spec = method_spec.get('parameters', {})

        for name, value in args.items():
            if name not in params_spec:
                converted[name] = value
                continue

            param_type = params_spec[name].get('type', 'str')
            try:
                converted[name] = self._convert_parameter(value, param_type)
            except (ValueError, TypeError, json.JSONDecodeError):
                converted[name] = value

        return converted

    def _list_methods(self, methods: list, plugin_name: str):
        """Display available methods and their specifications."""
        self.stdout.write(self.style.MIGRATE_HEADING(f'Metodi disponibili per {plugin_name}:'))
        for m in methods:
            self.stdout.write(self.style.NOTICE(f"- {m['name']}: {m.get('description', '')}"))
            params = m.get('parameters', {})
            if params:
                self.stdout.write('  Parametri:')
                for k, v in params.items():
                    self.stdout.write(f"    - {k}: {v}")

    def _execute_method(self, agent: Any, method_name: str, args: Dict[str, Any],
                        spec: Dict[str, Any], dry_run: bool = False) -> bool:
        """Execute a single method with error handling. Returns success status."""
        self.stdout.write(self.style.WARNING(
            f'Chiamata {method_name} con args: {json.dumps(args, ensure_ascii=False)}'
        ))

        if dry_run:
            return True

        if not hasattr(agent, method_name):
            self.stdout.write(self.style.ERROR(f"Metodo {method_name} non implementato"))
            return False

        try:
            converted = self._convert_parameters(args, spec)
            self.stdout.write(self.style.NOTICE(
                f'Args convertiti: {[(k, type(v).__name__) for k, v in converted.items()]}'
            ))
            result = getattr(agent, method_name)(**converted)
            self.stdout.write(self.style.SUCCESS(
                f'Result {method_name}: {json.dumps(result, ensure_ascii=False, default=str, indent=2)}'
            ))
            return True
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'Errore eseguendo {method_name}: {e}'))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            return False

    def _auto_run_methods(self, agent: Any, methods: list, dry_run: bool):
        """Execute all available methods with default parameters."""
        self.stdout.write(self.style.NOTICE('Esecuzione automatica dei metodi disponibili'))

        for m in methods:
            name = m['name']
            params = m.get('parameters', {})
            call_args = {
                pname: self._get_default_value(pname, pspec)
                for pname, pspec in params.items()
            }
            self._execute_method(agent, name, call_args, m, dry_run)

    def _run_single_method(self, agent: Any, method_name: str,
                           method_spec: Dict[str, Any], args_json: Optional[str], dry_run: bool):
        """Execute a single specified method."""
        raw_args = self._parse_args_json(args_json)

        # Apply defaults if no args provided
        if not raw_args:
            raw_args = {
                pname: pspec['default']
                for pname, pspec in method_spec.get('parameters', {}).items()
                if 'default' in pspec
            }

        self._execute_method(agent, method_name, raw_args, method_spec, dry_run)

    def handle(self, *args, **options):
        plugin_choice = options.get('plugin', 'agent')

        plugin_map = {
            'agent': AgentPlugins,
            'tutorial': TutorialAgentPlugins,
            'post': PostAgentPlugins,
        }

        if plugin_choice not in plugin_map:
            self.stdout.write(self.style.ERROR('Plugin non valido scelto'))
            return

        plugin_class = plugin_map[plugin_choice]
        methods = plugin_class.get_available_methods()
        method_dict = {m['name']: m for m in methods}
        agent = plugin_class()

        if options['list']:
            self._list_methods(methods, plugin_choice)
            return

        if options['auto_run']:
            self._auto_run_methods(agent, methods, options['dry_run'])
            return

        method_name = options.get('method')
        if method_name:
            if method_name not in method_dict:
                self.stdout.write(self.style.ERROR(
                    f'Metodo {method_name} non trovato. Usa --list per vedere i metodi disponibili'
                ))
                return

            self._run_single_method(
                agent, method_name, method_dict[method_name],
                options.get('args_json'), options['dry_run']
            )
            return

        self.stdout.write(self.style.NOTICE('Nessuna azione specificata. Usa --list, --method o --auto-run'))