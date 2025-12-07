SELL_DISCUSSION_PROMPT = """Il tuo compito è generare un json con un elevato numero di domande e risposte alternate, che serviranno per addestrare un assistente virtuale di un ecommerce. L\'obiettivo è insegnare all\'assistente a rispondere alle domande relative a questo prodotto "{text}". 
L\'assistente deve aspettare le domande del cliente. Il cliente é il soggetto che pone le domande e comincia la conversazione. 
Il cliente potrebbe non conoscere la tipologia di prodotto ma necessita comunque di una soluzione per svolgere l\'attività che il prodotto soddisfa. Inizia la conversazione con la manifestazione di questa necessità, come ad esempio "Avete [qualcosa|prodotto|soluzione|] per [fare qualcosa]?" 
La domanda successiva invece presuppone che il cliente sia più informato e chieda in maniera più specifica, come ad esempio: 
"Avete [prodotto] [per fare qualcosa|con determinata caratteristica]?"
A questo punto il prodotto è stato presentato e il cliente s\'informa circa le sue caratteristiche, in primo luogo il prezzo, con le classica domanda "Quanto costa [prodotto]?".
Se il prodotto presenta delle varianti|combinazioni, le domande devono coprire le caratteristiche delle combinazioni, con esito positivo, come ad esempio: 
"Il [prodotto] è disponibile [con determinata caratteristica]?", "È possibile averlo [colore]?"
Aggiungi anche domande specifiche che non sono soddisfabili, come ad esempio colori non disponibili o caratteristiche non elencate.
Formato JSON richiesto: {example_json}
È vietato aggiungere chiavi, elementi estranei al formato specificato o fornire output non richiesto.
"""

