# Liebesroman-Pipeline

Szenenweise Erzeugung von Langform-Prosa mit Story-Bibel und Prüfschleife.
Stand: Schritt 1 und 3 des Handoffs. Kein Web, keine Accounts, keine Datenbank,
keine eigene Hardware. Ein Kommandozeilenwerkzeug, das gegen einen
OpenAI-kompatiblen Endpunkt spricht.

## Warum als CLI und nicht als Website

Die offene Frage ist nicht, ob ein Modell eine schöne Szene schreibt. Das kann
fast jedes große Modell. Die offene Frage ist, ob Szene 28 noch weiß, dass er in
Szene 4 gelogen hat. Das zeigt sich nur mit Akte und Szenenschleife, und dafür
braucht es keine Oberfläche. Alles Weitere baut auf dieser Antwort auf.

## Einrichten

Kein Server, keine GPU. Ein Konto bei einem Anbieter, der offene Modelle pro
Token abrechnet, reicht.

```
pip install -r requirements.txt
cp .env.example .env      # LR_API_KEY eintragen
```

Der Endpunkt ist frei wählbar. Alles, was die OpenAI-Chat-API spricht,
funktioniert: OpenRouter, Together, DeepInfra, ein vLLM auf einem gemieteten
Pod, oder llama.cpp lokal. Nur `LR_BASE_URL` ändern.

Ohne Schlüssel läuft alles mit `--provider mock` als Trockenlauf. Damit lässt
sich die Mechanik prüfen, nicht die Prosa.

## Eine Geschichte schreiben

```
python3 -m liebesroman.cli init meine --vorlage vorlagen/beispiel.json
python3 -m liebesroman.cli weiter meine -n 5
python3 -m liebesroman.cli status meine
python3 -m liebesroman.cli akte meine
python3 -m liebesroman.cli lesen meine --datei meine.md
```

Alles liegt unter `stories/<name>/`: die Akte als `akte.json`, jede Szene
einzeln unter `szenen/`, jeder Modellaufruf mit vollem Prompt in `calls.jsonl`.
Die Protokolldatei ist beim Prompt-Tuning das wichtigste Werkzeug, weil man dort
sieht, was das Modell tatsächlich gelesen hat.

## Modelle vergleichen

```
python3 -m liebesroman.cli modelle "mistral"
python3 -m liebesroman.cli vergleich lauf1 \
    mistralai/mistral-small-3.2-24b-instruct \
    meta-llama/llama-3.3-70b-instruct
```

`modelle` fragt die Liste live beim Endpunkt ab, mit Kontextlänge und Preis je
Million Token. Das ist verlässlicher als jede Liste in einer Dokumentation.

`vergleich` schickt dasselbe Testset an alle genannten Modelle und legt die
Ergebnisse **blind** ab: In `vergleiche/<name>/blind.md` heißen die Modelle A, B,
C, und die Zuordnung ist pro Auftrag neu gemischt. Erst lesen und in
`bewertung.md` benoten, dann `zuordnung.json` öffnen. Wer den Namen kennt,
bewertet den Namen mit.

Nur einzelne Kategorien prüfen:

```
python3 -m liebesroman.cli vergleich schnell modell-a modell-b --nur 09_verweigerung 10_explizit_qualitaet
```

## Das Testset

`testset/basis.json` enthält zehn feste Szenenaufträge auf derselben Akte, jeder
auf genau eine Fähigkeit gerichtet: Figurenkonstanz, Rückbezug, räumliche
Kohärenz, Faktentreue, Dialog, Wiederholung, Register, Zeitführung,
Bereitschaft, explizites Register.

Zwei davon sind Fallen. Auftrag 04 lädt das Modell ein, gegen zwei Weltfakten zu
verstoßen, ohne es zu erwähnen. Auftrag 06 lädt es ein, verbrauchte Bilder aus
der Akte zu wiederholen.

## Aufbau

- `bible.py` — die Akte. Strukturierter Zustand, gedeckelt, damit sie vollständig
  in den Kontext passt. `render_kompakt` erzeugt daraus die Prompt-Fassung.
- `prompts.py` — Systemprompts pro Rolle, Stilbeispiele, Banliste. Stil kommt
  über Beispieltexte, nicht über Regeln.
- `pipeline.py` — die Schleife: planen, schreiben, prüfen, Akte fortschreiben.
  Bei harten Widersprüchen wird die Szene mit der Fehlerliste neu erzeugt.
- `vergleich.py` — Testset über mehrere Modelle, blind abgelegt.
- `llm.py` — Endpunkt-Client. Entfernt Sampler-Parameter, die ein Endpunkt nicht
  kennt, statt daran zu scheitern.

## Stil anpassen

`liebesroman/stil/beispiel_01.txt` und `beispiel_02.txt` gehen wörtlich in jeden
Schreib-Prompt. Sie sind der stärkste Hebel auf den Ton, deutlich stärker als
jede Anweisung im Systemprompt. Austauschen kostet nichts und wirkt sofort.

`banliste_de.txt` sammelt Wendungen, die in diesem Genre totgeschrieben sind.
Sie gehen als Verbotsliste in den Prompt und werden nach der Erzeugung noch
einmal nachgeprüft. Ein Treffer löst einen Neuversuch aus.

## Noch nicht gebaut

- Vektorsuche über alte Szenen für Rückbezüge, nötig ab etwa 50.000 Wörtern.
- Szenen-Zustand innerhalb einer Szene (Position, Kleidung), der die räumliche
  Kohärenz in expliziten Szenen stabilisiert.
- Mehrfachgenerierung mit Auswahl der besten Variante. Der Schalter
  `varianten` liegt in der Konfiguration, die Auswahl fehlt.
- Alles ab Schritt 5 des Handoffs: eigener Writer-Pod, Oberfläche, Accounts,
  Altersgate.
