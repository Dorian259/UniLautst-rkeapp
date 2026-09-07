"""Erzeugt aus einem Vergleichslauf eine Leseprobe für Testleserinnen.

Der Unterschied zum Blindvergleich: Hier geht es nicht um Fehlersuche, sondern
um Wirkung. Deshalb keine Kennzahlen, keine Banlisten-Treffer, keine
Auftragsbeschreibung im Text, nur die Prosa und zwei Fragen dazu.

Die Zuordnung ist über das ganze Paket fest, damit am Ende eine Rangfolge
möglich ist. Wer welchen Buchstaben hat, steht nur in der Schlüsseldatei.
"""

from __future__ import annotations

import html
import json
import random
from pathlib import Path

KOPF = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Leseprobe</title>
<style>
  :root {
    color-scheme: light dark;
    --grund: #fbfaf8;
    --papier: #ffffff;
    --schrift: #23201d;
    --leise: #6b645c;
    --linie: #e2ddd6;
    --akzent: #7a4a3a;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --grund: #16151a;
      --papier: #1e1d23;
      --schrift: #e8e4de;
      --leise: #9a938a;
      --linie: #33313a;
      --akzent: #d09a86;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--grund);
    color: var(--schrift);
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .huelle { max-width: 40rem; margin: 0 auto; padding: 1.5rem 1.25rem 5rem; }
  h1 { font-size: 1.5rem; line-height: 1.25; margin: 0 0 .75rem; }
  h2 {
    font-size: .8rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--leise); margin: 3rem 0 .5rem; font-weight: 600;
  }
  h3 { font-size: 1.1rem; margin: 2rem 0 .25rem; }
  .anleitung {
    background: var(--papier); border: 1px solid var(--linie);
    border-radius: .6rem; padding: 1rem 1.15rem; margin-bottom: 1rem;
  }
  .anleitung p { margin: .5rem 0; }
  .anleitung p:first-child { margin-top: 0; }
  .anleitung p:last-child { margin-bottom: 0; }
  .warnung { color: var(--akzent); font-weight: 600; }
  .text {
    background: var(--papier); border: 1px solid var(--linie);
    border-radius: .6rem; padding: 1.25rem 1.4rem; margin: .75rem 0 1rem;
    font-family: Georgia, "Iowan Old Style", "Times New Roman", serif;
    font-size: 1.06rem; line-height: 1.75;
  }
  .text p { margin: 0 0 1em; }
  .text p:last-child { margin-bottom: 0; }
  .frage { margin: 1rem 0 1.5rem; }
  .frage > span { display: block; font-size: .92rem; color: var(--leise); margin-bottom: .4rem; }
  .noten { display: flex; gap: .4rem; flex-wrap: wrap; }
  .noten label {
    flex: 1 1 3rem; min-width: 2.8rem; text-align: center;
    border: 1px solid var(--linie); border-radius: .45rem;
    padding: .55rem .2rem; cursor: pointer; background: var(--papier);
    font-variant-numeric: tabular-nums;
  }
  .noten input { position: absolute; opacity: 0; pointer-events: none; }
  .noten input:checked + span { font-weight: 700; }
  .noten label:has(input:checked) {
    border-color: var(--akzent); color: var(--akzent);
    box-shadow: inset 0 0 0 1px var(--akzent);
  }
  .skala { display: flex; justify-content: space-between; font-size: .78rem; color: var(--leise); margin-top: .3rem; }
  textarea, select {
    width: 100%; font: inherit; padding: .6rem .7rem; border-radius: .45rem;
    border: 1px solid var(--linie); background: var(--papier); color: inherit;
  }
  textarea { min-height: 4.5rem; resize: vertical; }
  button {
    font: inherit; font-weight: 600; padding: .8rem 1.2rem; border-radius: .5rem;
    border: 0; background: var(--akzent); color: var(--grund); cursor: pointer;
    width: 100%; margin-top: .5rem;
  }
  #ausgabe {
    white-space: pre-wrap; background: var(--papier); border: 1px solid var(--linie);
    border-radius: .5rem; padding: 1rem; margin-top: 1rem; font-size: .9rem;
    font-family: ui-monospace, Menlo, Consolas, monospace;
  }
  hr { border: 0; border-top: 1px solid var(--linie); margin: 2.5rem 0; }
  .fuss { color: var(--leise); font-size: .85rem; margin-top: 2rem; }
</style>
"""

JS = """
<script>
(function () {
  var SCHLUESSEL = "leseprobe-antworten";
  function felder() { return document.querySelectorAll("[data-feld]"); }

  try {
    var alt = JSON.parse(localStorage.getItem(SCHLUESSEL) || "{}");
    felder().forEach(function (el) {
      var n = el.getAttribute("data-feld");
      if (alt[n] === undefined) return;
      if (el.type === "radio") { el.checked = (el.value === alt[n]); }
      else { el.value = alt[n]; }
    });
  } catch (e) {}

  function sichern() {
    var daten = {};
    felder().forEach(function (el) {
      var n = el.getAttribute("data-feld");
      if (el.type === "radio") { if (el.checked) daten[n] = el.value; }
      else if (el.value) { daten[n] = el.value; }
    });
    try { localStorage.setItem(SCHLUESSEL, JSON.stringify(daten)); } catch (e) {}
    return daten;
  }

  document.addEventListener("input", sichern);
  document.addEventListener("change", sichern);

  document.getElementById("fertig").addEventListener("click", function () {
    var daten = sichern();
    var zeilen = ["Leseprobe, Antworten von: " + (daten["name"] || "(kein Name)"), ""];
    document.querySelectorAll("[data-block]").forEach(function (block) {
      zeilen.push(block.getAttribute("data-block"));
      block.querySelectorAll("[data-feld]").forEach(function (el) {
        var n = el.getAttribute("data-feld");
        var frage = el.getAttribute("data-frage") || n;
        if (el.type === "radio") { if (el.checked) zeilen.push("  " + frage + ": " + el.value); }
        else if (el.value) { zeilen.push("  " + frage + ": " + el.value); }
      });
      zeilen.push("");
    });
    var feld = document.getElementById("ausgabe");
    feld.textContent = zeilen.join("\\n");
    feld.hidden = false;
    feld.scrollIntoView({ behavior: "smooth", block: "start" });
    if (navigator.clipboard) {
      navigator.clipboard.writeText(feld.textContent).then(function () {
        document.getElementById("fertig").textContent = "Kopiert, schick es Dorian";
      }, function () {});
    }
  });
})();
</script>
"""


def _absaetze(text: str) -> str:
    teile = [t.strip() for t in text.split("\n\n") if t.strip()]
    return "\n".join(f"<p>{html.escape(t).replace(chr(10), '<br>')}</p>" for t in teile)


def _noten(feld: str, frage: str, links: str, rechts: str) -> str:
    knoepfe = "".join(
        f'<label><input type="radio" name="{feld}" value="{n}" '
        f'data-feld="{feld}" data-frage="{html.escape(frage)}"><span>{n}</span></label>'
        for n in range(1, 6)
    )
    return (
        f'<div class="frage"><span>{html.escape(frage)}</span>'
        f'<div class="noten">{knoepfe}</div>'
        f'<div class="skala"><span>{html.escape(links)}</span>'
        f'<span>{html.escape(rechts)}</span></div></div>'
    )


def _text_feld(feld: str, frage: str, platzhalter: str = "") -> str:
    return (
        f'<div class="frage"><span>{html.escape(frage)}</span>'
        f'<textarea data-feld="{feld}" data-frage="{html.escape(frage)}" '
        f'placeholder="{html.escape(platzhalter)}"></textarea></div>'
    )


def bauen(
    lauf_ordner: Path,
    testset_pfad: Path,
    modelle: list[str],
    ziel: Path,
    titel: str = "Leseprobe",
) -> tuple[Path, Path]:
    rohdaten = json.loads((lauf_ordner / "rohdaten.json").read_text(encoding="utf-8"))
    zuordnung = json.loads((lauf_ordner / "zuordnung.json").read_text(encoding="utf-8"))
    testset = json.loads(testset_pfad.read_text(encoding="utf-8"))

    # Feste, neu gemischte Zuordnung über das ganze Paket. Neu gemischt, damit
    # die Vorsortierung des Auftraggebers nicht durchschlägt.
    gemischt = modelle[:]
    random.shuffle(gemischt)
    paket_zuordnung = {chr(ord("A") + i): m for i, m in enumerate(gemischt)}

    def text_von(auftrag_id: str, modell: str) -> str:
        for buchstabe, m in (zuordnung.get(auftrag_id) or {}).items():
            if m == modell:
                return (rohdaten.get(auftrag_id, {}).get(buchstabe) or {}).get("text", "")
        return ""

    teile = [KOPF, '<div class="huelle">']
    teile.append(f"<h1>{html.escape(titel)}</h1>")
    teile.append(
        '<div class="anleitung">'
        "<p>Danke, dass du das liest. Es geht um eine Sache: Welche der drei "
        "Versionen liest sich am besten?</p>"
        "<p>Du siehst drei Szenen aus derselben Geschichte. Jede Szene gibt es "
        "dreimal, geschrieben von A, B und C. Die Reihenfolge bleibt gleich, A ist "
        "immer derselbe Schreiber.</p>"
        "<p>Lies einfach und antworte spontan. Es gibt keine richtige Antwort, "
        "und du musst nichts begründen, was du nicht begründen willst. Dauert "
        "etwa 20 Minuten.</p>"
        '<p class="warnung">Die dritte Szene ist explizit. Wenn du das nicht lesen '
        "willst, überspring sie und sag bei den letzten Fragen Bescheid.</p>"
        "<p>Am Ende auf den Knopf, dann wird deine Antwort kopiert und du kannst "
        "sie zurückschicken. Deine Eingaben bleiben auf deinem Gerät.</p>"
        "</div>"
    )
    teile.append(
        '<div class="frage"><span>Dein Name oder Kürzel</span>'
        '<textarea data-feld="name" data-frage="Name" style="min-height:2.5rem"></textarea></div>'
    )

    for auftrag in testset["auftraege"]:
        aid = auftrag["id"]
        teile.append("<hr>")
        teile.append(f'<h2>Szene {html.escape(auftrag["kategorie"])}</h2>')
        for buchstabe in sorted(paket_zuordnung):
            modell = paket_zuordnung[buchstabe]
            text = text_von(aid, modell)
            if not text.strip():
                continue
            teile.append(f'<div data-block="{html.escape(auftrag["kategorie"])} / {buchstabe}">')
            teile.append(f"<h3>{buchstabe}</h3>")
            teile.append(f'<div class="text">{_absaetze(text)}</div>')
            teile.append(
                _noten(
                    f"{aid}_{buchstabe}_note",
                    "Wie gern hast du das gelesen?",
                    "gar nicht",
                    "sehr gern",
                )
            )
            teile.append(
                _text_feld(
                    f"{aid}_{buchstabe}_notiz",
                    "Was ist dir aufgefallen? (optional)",
                    "Ein Satz reicht.",
                )
            )
            teile.append("</div>")

    teile.append("<hr>")
    teile.append("<h2>Zum Schluss</h2>")
    teile.append('<div data-block="Gesamt">')
    buchstaben = "".join(
        f'<option value="{b}">{b}</option>' for b in sorted(paket_zuordnung)
    )
    teile.append(
        '<div class="frage"><span>Von wem würdest du ein ganzes Buch lesen?</span>'
        f'<select data-feld="gesamt_favorit" data-frage="Favorit">'
        f'<option value="">bitte wählen</option>{buchstaben}</select></div>'
    )
    teile.append(
        _text_feld(
            "gesamt_ki",
            "Hat irgendetwas nach Maschine geklungen? Wenn ja, wo genau?",
            "Ein Wort, ein Satz, eine Stelle.",
        )
    )
    teile.append(
        _text_feld(
            "gesamt_genre",
            "Klingt das wie das, was du sonst liest, oder wie eine Nachahmung davon?",
            "",
        )
    )
    teile.append(
        _text_feld("gesamt_frei", "Sonst noch etwas? (optional)", "")
    )
    teile.append("</div>")
    teile.append('<button id="fertig" type="button">Antworten fertig, kopieren</button>')
    teile.append('<div id="ausgabe" hidden></div>')
    teile.append(
        '<p class="fuss">Nichts von dem, was du hier eintippst, wird irgendwohin '
        "gesendet. Die Datei läuft nur in deinem Browser.</p>"
    )
    teile.append("</div>")
    teile.append(JS)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text("\n".join(teile), encoding="utf-8")

    schluessel = ziel.parent / (ziel.stem + "_schluessel.json")
    schluessel.write_text(
        json.dumps(paket_zuordnung, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ziel, schluessel
