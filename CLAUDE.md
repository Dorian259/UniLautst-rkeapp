# Projektkontext

Selbst gehostete Plattform, auf der sich Leserinnen fortlaufend eine
personalisierte Liebesgeschichte erzeugen lassen. Genre Romance und Spicy
Romance, Sprache Deutsch. Der Anspruch ist gute Prosa, detailreich, über die
gesamte Länge kohärent, ohne Wiederholungen.

Der Betreiber heißt Dorian. Er ist kein Berufsentwickler. Erklärungen einfach
halten, Befehle zum Kopieren geben, Fachbegriffe beim ersten Mal erklären.

## Stand

Gebaut ist Schritt 1: die Erzeugungspipeline als Kommandozeilenwerkzeug. Kein
Web, keine Accounts, keine Datenbank, keine eigene Hardware. Details in
README.md, die zuerst lesen.

## Wo es gerade steht

Als Nächstes läuft das Grobsieb: fünf bis sechs Modelle über
`testset/spicy.json`, dann `./lr sieben`, dann bleiben drei übrig.

Danach in dieser Reihenfolge:

1. Stilbeispiele austauschen. Dorian fragt Testleserinnen nach zwei bis drei
   Passagen aus ihren Lieblingsbüchern. Die ersetzen
   `liebesroman/stil/beispiel_01.txt` und `beispiel_02.txt`. Das ist der
   stärkste Hebel auf den Ton, stärker als ein Modellwechsel um eine
   Größenklasse.
2. `./lr lesepaket` an die Testleserinnen. **Sie** entscheiden, welches Modell,
   nicht Dorian und nicht wir. Er ist nicht die Zielgruppe.
3. Lange Geschichte mit dem Sieger, 20 bis 30 Szenen, von Dorian am Stück
   gelesen. Seine Befundliste ist die Grundlage für alles Weitere.
4. Pipeline auf Kohärenz tunen, iterativ.

Die offene Kernfrage, an der die spätere Hardwarerechnung hängt: reicht die
24B-Klasse oder braucht es 70B.

## Arbeitsteilung bei der Modellwahl

Handwerk lässt sich messen und entscheidet sich hier: Verweigerung,
Faktenwiderspruch, räumliche Fehler, Wiederholung. Dafür gibt es `./lr sieben`.

Wirkung lässt sich nicht messen und entscheiden die Testleserinnen. Nie
Modellnamen oder eine Vorauswahl mit in die Leseprobe geben, sonst bewerten sie
die Erwartung mit.

## Diagnose, wenn eine lange Geschichte auseinanderfällt

`stories/<name>/calls.jsonl` enthält jeden Modellaufruf mit vollem Prompt.

- Der Fakt stand in der Akte und das Modell hat ihm widersprochen: Modellfehler.
- Der Fakt stand nicht in der Akte: Pipelinefehler, der Aktenführer hat ihn
  nicht eingetragen.

Das ist ablesbar, nicht zu raten.

## Konventionen

**Deutsche Texte immer mit echten Umlauten**, also ä ö ü ß, nie ae oe ue ss.
Das gilt für Prompts, Stilbeispiele, Testsets, Vorlagen und Ausgaben. Grund:
Was im Kontext steht, imitiert das Modell. Ein Prompt in Ersatzschreibung
erzeugt Prosa in Ersatzschreibung. Ausgenommen sind Python-Bezeichner und
JSON-Schlüssel, die bleiben ASCII, weil Modelle ASCII-Schlüssel zuverlässiger
reproduzieren.

Keine typografischen Anführungszeichen und keine Gedankenstriche, weder im Code
noch in Antworten.

**Der API-Schlüssel gehört ausschließlich in die lokale `.env`.** Nie ins
Repository, nie in eine Datei, die weitergegeben wird, nie in eine Antwort.

**Stil kommt über Beispiele, nicht über Regeln.** Der Systemprompt des
Schreibers bleibt kurz. Ein langer Regelkatalog erzeugt Regelbefolgungsverhalten
statt Prosa. Das war der Fehler in Dorians erstem Versuch.

**Sampler:** Repetition Penalty niedrig halten, 1.05 bis 1.10. Höhere Werte
führen dazu, dass das Modell feste Figurenmerkmale fallen lässt, nur um sich
nicht zu wiederholen.

Prüfer und Aktenführer arbeiten auf der neutralen Szenenzusammenfassung, nicht
auf dem Rohtext. Das spart Tokens und vermeidet Verweigerungen bei
Klassifikationsaufgaben über explizitem Material.

## Was bewusst noch nicht gebaut ist

Vektorsuche über alte Szenen für Rückbezüge, nötig ab etwa 50.000 Wörtern. Ein
Zustand innerhalb einer Szene für die räumliche Kohärenz. Mehrfachgenerierung
mit Auswahl der besten Variante.

Alle drei erst bauen, wenn Schritt 3 zeigt, dass sie gebraucht werden. Vorher
wäre es geraten.

## Später, nicht jetzt

Eigener Writer-Pod für den expliziten Teil, weil Per-Token-Anbieter das in ihren
Nutzungsbedingungen meist ausschließen. Weboberfläche und Accounts.
Altersnachweis, Zahlungsanbieter und Monetarisierung, erst nach anwaltlicher
Beratung, weil die Antwort das Produktdesign bestimmt und nachträglich nicht
einbaubar ist.

Die Kohärenz ist das Projekt, nicht die Oberfläche. Die Oberfläche ist bekannte
Arbeit, die Kohärenz über achtzig Szenen ist der Teil, an dem es scheitern kann.
