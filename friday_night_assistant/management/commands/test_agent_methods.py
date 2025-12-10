from django.core.management.base import BaseCommand
from typing import Any, Dict, Optional
import json
import logging

from friday_night_assistant.plugins import AgentPlugins

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test helper per eseguire i metodi esposti dall'agente (AgentPlugins)"

    def add_arguments(self, parser):
        parser.add_argument('--list', action='store_true', help='Elenca i metodi disponibili e la loro specifica')
        parser.add_argument('--method', type=str, help='Nome del metodo da eseguire (deve essere tra quelli esposti da get_available_methods)')
        parser.add_argument('--args-json', dest='args_json', type=str, help='Argomenti JSON da passare al metodo (es: "{\"site_id\":1}")')
        parser.add_argument('--auto-run', action='store_true', help='Esegue tutti i metodi esposti da get_available_methods con valori di default/sostitutivi')
        parser.add_argument('--dry-run', action='store_true', help='Non esegue realmente i metodi, mostra solo cosa verrebbe chiamato')

    def _parse_args_json(self, args_str: Optional[str]) -> Dict[str, Any]:
        if not args_str:
            return {}
        try:
            return json.loads(args_str)
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Errore parsing JSON args: {e}'))
            return {}

    def _get_default_for_param(self, name: str, spec: Dict[str, Any]) -> Any:
        if 'default' in spec:
            return spec['default']
        ptype = spec.get('type', 'str')
        if ptype == 'int':
            if name == 'site_id':
                return 1
            return 0
        if ptype == 'bool':
            return False
        if ptype == 'list':
            return []
        if ptype == 'dict':
            return {}
        return 'sample-slug'

    def _convert_parameter_types(self, args: Dict[str, Any], method_spec: Dict[str, Any]) -> Dict[str, Any]:
        converted_args: Dict[str, Any] = {}
        parameters_spec = method_spec.get('parameters', {})

        for param_name, param_value in args.items():
            if param_name not in parameters_spec:
                converted_args[param_name] = param_value
                continue
            param_type = parameters_spec[param_name].get('type', 'str')
            try:
                if param_value is None:
                    converted_args[param_name] = None
                elif param_type == 'int':
                    converted_args[param_name] = int(param_value)
                elif param_type == 'float':
                    converted_args[param_name] = float(param_value)
                elif param_type == 'bool':
                    if isinstance(param_value, str):
                        converted_args[param_name] = param_value.lower() in ('true', '1', 'yes')
                    else:
                        converted_args[param_name] = bool(param_value)
                elif param_type == 'list':
                    if isinstance(param_value, str):
                        try:
                            converted_args[param_name] = json.loads(param_value)
                        except json.JSONDecodeError:
                            converted_args[param_name] = [item.strip() for item in param_value.split(',')]
                    elif isinstance(param_value, list):
                        converted_args[param_name] = param_value
                    else:
                        converted_args[param_name] = [param_value]
                elif param_type == 'dict':
                    if isinstance(param_value, str):
                        converted_args[param_name] = json.loads(param_value)
                    else:
                        converted_args[param_name] = param_value
                else:
                    converted_args[param_name] = str(param_value)
            except (ValueError, TypeError, json.JSONDecodeError):
                converted_args[param_name] = param_value

        return converted_args

    def handle(self, *args, **options):
        # Usa solo la lista definita da get_available_methods()
        methods = AgentPlugins.get_available_methods()
        method_dict = {m['name']: m for m in methods}

        agent = AgentPlugins()

        if options['list']:
            self.stdout.write(self.style.MIGRATE_HEADING('Metodi disponibili per AgentPlugins:'))
            for m in methods:
                self.stdout.write(self.style.NOTICE(f"- {m['name']}: {m.get('description','')}") )
                params = m.get('parameters', {})
                if params:
                    self.stdout.write('  Parametri:')
                    for k, v in params.items():
                        self.stdout.write(f"    - {k}: {v}")
            return

        if options['auto_run']:
            self.stdout.write(self.style.NOTICE('Esecuzione automatica dei metodi esposti da get_available_methods'))
            for m in methods:
                name = m['name']
                spec = m
                params = spec.get('parameters', {})
                call_args = {}
                for pname, pspec in params.items():
                    call_args[pname] = self._get_default_for_param(pname, pspec)

                self.stdout.write(self.style.WARNING(f'Chiamata {name} con args: {json.dumps(call_args, ensure_ascii=False)}'))
                if options['dry_run']:
                    continue
                # Non tentiamo di invocare metodi non esposti
                if not hasattr(agent, name):
                    self.stdout.write(self.style.ERROR(f"Metodo {name} non presente su AgentPlugins, salto."))
                    continue
                try:
                    converted = self._convert_parameter_types(call_args, spec)
                    result = getattr(agent, name)(**converted)
                    self.stdout.write(self.style.SUCCESS(f'Result {name}: {json.dumps(result, ensure_ascii=False, default=str, indent=2)}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Errore eseguendo {name}: {e}'))
            return

        method = options.get('method')
        if method:
            if method not in method_dict:
                self.stdout.write(self.style.ERROR(f'Metodo {method} non trovato. Usa --list per vedere i metodi disponibili'))
                return
            spec = method_dict[method]
            raw_args = self._parse_args_json(options.get('args_json'))

            if not raw_args:
                for pname, pspec in spec.get('parameters', {}).items():
                    if 'default' in pspec:
                        raw_args[pname] = pspec['default']

            self.stdout.write(self.style.WARNING(f'Chiamata {method} con args RAW: {json.dumps(raw_args, ensure_ascii=False)}'))
            if options['dry_run']:
                return

            if not hasattr(agent, method):
                self.stdout.write(self.style.ERROR(f'Metodo {method} non implementato su AgentPlugins'))
                return

            try:
                converted_args = self._convert_parameter_types(raw_args, spec)
                self.stdout.write(self.style.NOTICE(f'Args convertiti: {[(k, type(v).__name__) for k, v in converted_args.items()]}'))
                result = getattr(agent, method)(**converted_args)
                self.stdout.write(self.style.SUCCESS(f'Result {method}: {json.dumps(result, ensure_ascii=False, default=str, indent=2)}'))
            except Exception as e:
                import traceback
                self.stdout.write(self.style.ERROR(f'Errore eseguendo {method}: {e}'))
                self.stdout.write(self.style.ERROR(traceback.format_exc()))
            return

        self.stdout.write(self.style.NOTICE('Nessuna azione specificata. Usa --list, --method o --auto-run'))
