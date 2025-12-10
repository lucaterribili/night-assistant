# Sistema di Sotto-Agenti - Documentazione

## Architettura

Il sistema è composto da un **MainAgent** (run_agent) e due **sotto-agenti specializzati**:

1. **PostAgent** - Specializzato nella gestione dei blog post
2. **TutorialAgent** - Specializzato nella gestione dei tutorial

### Flusso di Esecuzione

```
┌─────────────────┐
│   MainAgent     │  ← Analizza Matomo, identifica contenuto problematico
│   (run_agent)   │
└────────┬────────┘
         │
         │ Delega in base al tipo
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌──────────────┐
│ Post   │  │ Tutorial     │
│ Agent  │  │ Agent        │
└────┬───┘  └──────┬───────┘
     │             │
     │ Autonomo    │ Autonomo
     │             │
     ▼             ▼
  Ritorna      Ritorna
  al Main      al Main
```

## Componenti Principali

### 1. MainAgent (run_agent)
**File**: `friday_night_assistant/management/commands/run_agent.py`

**Responsabilità**:
- Analizza i dati di Matomo per trovare contenuti con problemi (es. bounce rate alto)
- Identifica il tipo di contenuto (blog post o tutorial)
- Delega il lavoro al sotto-agente appropriato
- Riceve il risultato e decide se continuare o fermarsi

**Metodi principali**:
- `get_top_bounce_urls()` - Ottiene URL con bounce rate alto
- `get_post_by_slug()` - Trova un blog post
- `get_tutorial_by_slug()` - Trova un tutorial
- `delegate_to_post_agent()` - Delega a PostAgent
- `delegate_to_tutorial_agent()` - Delega a TutorialAgent

### 2. PostAgent
**File**: `friday_night_assistant/management/commands/run_post_agent.py`
**Plugin**: `friday_night_assistant/plugins/post_plugins.py`

**Responsabilità**:
- Riceve delega dal MainAgent per lavorare su un blog post specifico
- Decide autonomamente quali azioni eseguire
- Analizza il contenuto e la qualità del post
- Migliora il contenuto se necessario
- Ritorna il controllo al MainAgent quando completo

**Metodi disponibili**:
- `get_post_details(slug)` - Dettagli del post
- `update_post_content(slug, new_content)` - Aggiorna contenuto
- `get_post_categories(slug)` - Categorie del post
- `analyze_post_quality(slug)` - Analisi qualità

**Workflow tipico**:
1. `get_post_details` - Ottieni dettagli
2. `analyze_post_quality` - Analizza qualità
3. `get_post_categories` - Verifica categorie (opzionale)
4. `update_post_content` - Migliora se necessario
5. `stop: true` - Ritorna al MainAgent

### 3. TutorialAgent
**File**: `friday_night_assistant/management/commands/run_tutorial_agent.py`
**Plugin**: `friday_night_assistant/plugins/tutorial_plugins.py`

**Responsabilità**:
- Riceve delega dal MainAgent per lavorare su un tutorial specifico
- Decide autonomamente quali azioni eseguire
- Analizza struttura e completezza del tutorial
- Verifica prerequisiti e setup instructions
- Migliora il contenuto se necessario
- Ritorna il controllo al MainAgent quando completo

**Metodi disponibili**:
- `get_tutorial_details(slug)` - Dettagli del tutorial
- `update_tutorial_content(slug, new_content)` - Aggiorna contenuto
- `get_tutorial_categories(slug)` - Categorie del tutorial
- `analyze_tutorial_structure(slug)` - Analisi struttura
- `check_tutorial_prerequisites(slug)` - Verifica prerequisiti

**Workflow tipico**:
1. `get_tutorial_details` - Ottieni dettagli
2. `analyze_tutorial_structure` - Analizza struttura
3. `check_tutorial_prerequisites` - Verifica prerequisiti
4. `get_tutorial_categories` - Verifica categorie (opzionale)
5. `update_tutorial_content` - Migliora se necessario
6. `stop: true` - Ritorna al MainAgent

## Gestione della Memoria

Ogni agente ha la **propria memoria separata** identificata dal campo `agent_type`:

- **main** - Memoria del MainAgent
- **post** - Memoria del PostAgent
- **tutorial** - Memoria del TutorialAgent

### Modello AgentMemory

```python
class AgentMemory(models.Model):
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=255)
    agent_type = models.CharField(max_length=50, default='main')  # 'main', 'post', 'tutorial'
    value = models.JSONField()  # Contiene decisioni e risultati
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Metodi di gestione memoria (BaseSubAgent)

- `_get_previous_memories()` - Recupera memorie dell'agente specifico
- `_save_decision_to_memory(decision)` - Salva decisione
- `_update_memory_with_result(memory, result)` - Aggiorna con risultato
- `_clear_agent_memory()` - Pulisce memoria dell'agente

## Classe Base: BaseSubAgent

**File**: `friday_night_assistant/management/commands/base_subagent.py`

Fornisce funzionalità comuni a tutti i sotto-agenti:

### Funzionalità principali:

1. **Gestione memoria separata** per tipo di agente
2. **Loop decisionale** con LLM
3. **Conversione automatica** dei parametri
4. **Logging dettagliato** delle azioni
5. **Gestione errori** robusta
6. **Formattazione prompt** personalizzabile

### Metodi override-abili:

- `_build_prompt()` - Costruisce prompt specifico per l'agente
- `execute()` - Entry point programmatico

## Uso del Sistema

### Esempio 1: MainAgent trova e delega

```python
# MainAgent esegue:
bounce_urls = self.get_top_bounce_urls(site_id=1, limit=5)
# Risultato: [
#   {"url": "/blog/post-123", "type": "blog", "slug": "post-123", "bounce_rate": 85.5},
#   {"url": "/tutorial/python-intro", "type": "tutorial", "slug": "python-intro", "bounce_rate": 78.2}
# ]

# MainAgent delega a PostAgent
result = self.delegate_to_post_agent(slug="post-123", task="analyze_and_improve")
# PostAgent lavora autonomamente e ritorna:
# {
#   "success": True,
#   "agent": "PostAgent",
#   "slug": "post-123",
#   "last_action": {...}
# }

# MainAgent delega a TutorialAgent
result = self.delegate_to_tutorial_agent(slug="python-intro", task="analyze_and_improve")
# TutorialAgent lavora autonomamente e ritorna:
# {
#   "success": True,
#   "agent": "TutorialAgent",
#   "slug": "python-intro",
#   "last_action": {...}
# }
```

### Esempio 2: Esecuzione completa

```bash
# Esegui il MainAgent
python manage.py run_agent

# Il MainAgent:
# 1. Chiama get_top_bounce_urls()
# 2. Per ogni URL con bounce alto:
#    a. Identifica il tipo (blog/tutorial)
#    b. Estrae lo slug
#    c. Delega al sotto-agente appropriato
#    d. Riceve il risultato
#    e. Decide se continuare
```

## Vantaggi del Sistema

1. **Separazione delle responsabilità**: Ogni agente è specializzato
2. **Memoria isolata**: Nessuna interferenza tra agenti
3. **Autonomia**: I sotto-agenti decidono autonomamente
4. **Scalabilità**: Facile aggiungere nuovi sotto-agenti
5. **Manutenibilità**: Codice modulare e testabile
6. **Plugin specifici**: Ogni agente ha i suoi metodi specializzati

## Aggiungere un Nuovo Sotto-Agente

Per aggiungere un nuovo sotto-agente (es. "VideoAgent"):

1. **Crea il plugin**: `friday_night_assistant/plugins/video_plugins.py`
   - Classe `VideoAgentPlugins` con metodi specifici
   - Metodo `get_available_methods()` con la lista dei metodi

2. **Crea il comando**: `friday_night_assistant/management/commands/run_video_agent.py`
   - Eredita da `BaseSubAgent`
   - Imposta `AGENT_TYPE = "video"` e `AGENT_NAME = "VideoAgent"`
   - Override `_build_prompt()` se necessario
   - Implementa `execute(slug, task)`

3. **Aggiungi il metodo di delega** in `AgentPlugins`:
   ```python
   @staticmethod
   def delegate_to_video_agent(slug: str, task: str = 'analyze') -> Dict[str, Any]:
       from friday_night_assistant.management.commands.run_video_agent import Command
       video_agent = Command()
       return video_agent.execute(slug=slug, task=task)
   ```

4. **Aggiungi alla lista dei metodi disponibili** in `AgentPlugins.get_available_methods()`

## Note Tecniche

### Conversione Parametri
BaseSubAgent converte automaticamente i parametri in base alla specifica del metodo:
- `int`, `float`, `bool`, `str`, `list`, `dict`

### Gestione Errori
Gli errori vengono catturati e salvati nella memoria come:
```json
{
  "error": "messaggio di errore",
  "action": "metodo_fallito"
}
```

### Formato Decisione LLM
```json
{
  "action": "nome_metodo",
  "args": {"param1": "valore1"},
  "reason": "spiegazione della decisione",
  "stop": false
}
```

### Stop Condition
Quando un sotto-agente imposta `"stop": true`, il controllo ritorna al MainAgent.

## Migrations

Per applicare la migrazione del campo `agent_type`:

```bash
python manage.py migrate mysql_models
```

Questo aggiunge il campo `agent_type` alla tabella `AgentMemory` con indice su `(agent_type, created_at)`.

