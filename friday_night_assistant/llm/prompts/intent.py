INTENT_PROMPT = """Da questa domanda "{question.text}", dobbiamo estrarre l\'intento della domanda. 
L\'output deve comprendere un nome di sistema e un titolo leggibile.
Il nome deve essere in perfetto inglese e deve avere il prefisso utter_
Il titolo invece deve essere in perfetto italiano.
{intents_list_part}
Restituisci il risultato in formato JSON, come questo esempio.
Esempio di output JSON: {{"name": "utter_intent_name", "title": "Titolo intento"}}.
"""

