CORRECT_JSON_PROMPT = """Il tuo compito è correggere le predizioni di un modello PyTorch.
{task_part}
Il modello ha generato questa predizione: "{task_output}".
Il tuo compito è correggere l\'output del modello PyTorch.
Valuta la predizione e correggi gli errori, eliminando eventuali domande e risposte non pertinenti.{critical_part}
Inoltre devi evitare che vengano aggiunte domande e risposte che non sono presenti nel testo in input.
Assicurati che l\'output corretto sia nel formato richiesto, ovvero un array di domande e risposte alternate in sequenza.
"""

