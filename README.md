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
bash setup.sh
```

Das legt eine eigene Python-Umgebung an, installiert die Abhängigkeiten, fragt
nach dem Schlüssel und schreibt ihn in `.env`. Danach läuft alles über `./lr`
statt über den langen Python-Aufruf.

Der Schlüssel gehört ausschließlich in die lokale `.env`. Die Datei steht in
`.gitignore` und darf nie in ein Repository, in einen Chat oder in eine Datei,
die weitergegeben wird.

Der Endpunkt ist frei wählbar. Alles, was die OpenAI-Chat-API spricht,
funktioniert: OpenRouter, Together, DeepInfra, ein vLLM auf einem gemieteten
Pod, oder llama.cpp lokal. Nur `LR_BASE_URL` ändern.

Ohne Schlüssel läuft alles mit `--provider mock` als Trockenlauf. Damit lässt
sich die Mechanik prüfen, nicht die Prosa.

## Eine Geschichte schreiben

```
./lr init meine --vorlage vorlagen/beispiel.json --schreibmodell MODELL
./lr weiter meine -n 5
./lr status meine
./lr akte meine
./lr lesen meine --datei meine.md
```

Alles liegt unter `stories/<name>/`: die Akte als `akte.json`, jede Szene
einzeln unter `szenen/`, jeder Modellaufruf mit vollem Prompt in `calls.jsonl`.
Die Protokolldatei ist beim Prompt-Tuning das wichtigste Werkzeug, weil man dort
sieht, was das Modell tatsächlich gelesen hat.

## Modelle vergleichen

```
./lr modelle "mistral"
./lr vergleich lauf1 modell-a modell-b modell-c
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
./lr vergleich schnell modell-a modell-b --testset testset/spicy.json --nur s1_bereitschaft
```

## Leseprobe für Testleserinnen

Die handwerkliche Auswahl trifft man selbst, die Qualitätsentscheidung nicht.
Dafür baut `lesepaket` aus einem Lauf eine eigenständige HTML-Datei, die man
verschicken kann:

```
./lr vergleich probe modell-a modell-b modell-c --testset testset/leseprobe.json
./lr lesepaket probe modell-a modell-b modell-c
```

Die Datei enthält nur die Prosa, keine Modellnamen, keine Kennzahlen und keine
Auftragsbeschreibung. Die Zuordnung wird für das Paket neu gemischt, damit die
eigene Vorsortierung nicht durchschlägt, und liegt in einer Schlüsseldatei, die
nicht mitgeschickt wird.

Die Seite läuft ohne Internet und ohne Server. Eingaben bleiben im Browser der
Leserin, am Ende erzeugt ein Knopf einen Text zum Zurückschicken.

## Die Testsets

`testset/basis.json`, acht Aufträge, nicht explizit. Figurenkonstanz, Rückbezug,
räumliche Kohärenz, Faktentreue, Dialog, Wiederholung, Register und Nähe,
Zeitführung. Zwei davon sind Fallen: Auftrag 04 lädt das Modell ein, gegen zwei
Weltfakten zu verstoßen, ohne es zu erwähnen, Auftrag 06 lädt es ein,
verbrauchte Bilder aus der Akte zu wiederholen.

`testset/spicy.json`, sechs Aufträge, explizit, dieselben Figuren weiter
fortgeschritten. Gezielt auf die bekannten Schwächen kleiner Modelle in diesem
Register: verweigert es überhaupt, bleibt die räumliche Logik erhalten, wiederholt
sich das Vokabular über zwei Szenen, bleiben die Figuren unterscheidbar, kann es
eine Szene kippen lassen, braucht es den Vollzug für Spannung.

`testset/leseprobe.json`, drei Szenen in drei Tonlagen: romantisch, angedeutet,
explizit. Nicht zur Fehlersuche, sondern als Leseprobe für Testleserinnen.
Deshalb drei verschiedene Szenen statt derselben dreimal, damit es sich lesen
lässt.

Die Intensität steht in der Akte des Testsets, nicht im einzelnen Auftrag. Ein
Auftrag kann sie über das Feld `intensitaet` überschreiben. Ohne das liest das
Modell in der Akte "nicht explizit" und im Auftrag das Gegenteil, und der Test
misst dann den Widerspruch statt der Fähigkeit.

## Aufbau

- `bible.py` — die Akte. Strukturierter Zustand, gedeckelt, damit sie vollständig
  in den Kontext passt. `render_kompakt` erzeugt daraus die Prompt-Fassung.
- `prompts.py` — Systemprompts pro Rolle, Stilbeispiele, Banliste. Stil kommt
  über Beispieltexte, nicht über Regeln.
- `pipeline.py` — die Schleife: planen, schreiben, prüfen, Akte fortschreiben.
  Bei harten Widersprüchen wird die Szene mit der Fehlerliste neu erzeugt.
- `vergleich.py` — Testset über mehrere Modelle, blind abgelegt.
- `lesepaket.py` — erzeugt aus einem Lauf eine verschickbare Leseprobe.
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
