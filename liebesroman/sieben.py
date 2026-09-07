"""Automatische Vorauswertung eines Vergleichslaufs.

Das Grobsieb fragt nicht, ob ein Text schön ist, sondern ob er handwerklich
durchfällt. Das meiste davon ist zählbar, und was zählbar ist, muss niemand
lesen.

Die Ausgabe ist bewusst ein Hinweisgeber, kein Urteil. Ein Treffer heisst
"hier nachsehen", nicht "durchgefallen". Ein Faktencheck über Stichwörter
erzeugt zwangsläufig Fehlalarme, und ein stiller Fehlalarm wäre schlimmer als
ein lauter.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

# Formulierungen, mit denen Modelle einen Auftrag abbiegen, statt ihn zu
# erfuellen. Auf beiden Sprachen, weil viele Modelle bei Ablehnung ins
# Englische fallen.
VERWEIGERUNG = [
    "i can't", "i cannot", "i won't", "i'm not able to", "i am unable",
    "as an ai", "i'm sorry, but", "i apologize, but",
    "content policy", "i must decline", "not appropriate",
    "kann ich nicht", "darf ich nicht", "es tut mir leid, aber",
    "als ki ", "als sprachmodell", "kann ich leider nicht",
    "nicht angemessen", "ich lehne", "richtlinien",
]

# Ausweichmanoever: das Modell schreibt zwar, blendet aber an der Stelle ab,
# auf die es ankommt.
ABBLENDEN = [
    "später in dieser nacht", "am nächsten morgen wachte",
    "was dann geschah", "den rest der nacht",
    "die tür schloss sich hinter", "und dann verlor sie sich",
    "fade to black", "the rest of the night",
]

WORTMUSTER = re.compile(r"[a-zäöüß]+", re.IGNORECASE)

# Manche Modelle schreiben "naechsten" statt "nächsten". Ohne Normalisierung
# faellt so ein Text durch jedes Muster.
UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def normal(text: str) -> str:
    return text.lower().translate(UMSCHRIFT)


def _drei_gramme(text: str) -> set[tuple[str, ...]]:
    woerter = [w.lower() for w in WORTMUSTER.findall(text)]
    return {tuple(woerter[i : i + 3]) for i in range(len(woerter) - 2)}


def _ueberlappung(a: str, b: str) -> float:
    """Anteil der Dreiwortfolgen aus b, die auch in a vorkommen."""
    ga, gb = _drei_gramme(a), _drei_gramme(b)
    if not gb:
        return 0.0
    return len(ga & gb) / len(gb)


def _treffer(text: str, muster: list[str]) -> list[str]:
    klein = normal(text)
    return [m for m in muster if normal(m) in klein]


def _eigenwiederholung(text: str) -> list[str]:
    """Woerter, die im selben Text auffaellig oft vorkommen.

    Funktionswoerter sind ausgeschlossen, indem nur Woerter ab sieben Zeichen
    gezaehlt werden. Das reicht, um das typische Kreisen um immer dieselben
    zwei, drei Begriffe sichtbar zu machen.
    """
    woerter = [w.lower() for w in WORTMUSTER.findall(text) if len(w) >= 7]
    if len(woerter) < 40:
        return []
    haeufig = Counter(woerter).most_common(4)
    return [f"{w} ({n}x)" for w, n in haeufig if n >= 5]


def auswerten(lauf_ordner: Path, testset_pfad: Path) -> dict:
    rohdaten = json.loads((lauf_ordner / "rohdaten.json").read_text(encoding="utf-8"))
    zuordnung = json.loads((lauf_ordner / "zuordnung.json").read_text(encoding="utf-8"))
    testset = json.loads(testset_pfad.read_text(encoding="utf-8"))

    pruefregeln = testset.get("pruefregeln") or []
    auftrag_nach_id = {a["id"]: a for a in testset["auftraege"]}

    # Texte nach Modell sammeln, damit die Wiederholung zwischen zwei Szenen
    # desselben Modells messbar wird.
    nach_modell: dict[str, dict[str, dict]] = {}
    for aid, buchstaben in zuordnung.items():
        for buchstabe, modell in buchstaben.items():
            eintrag = (rohdaten.get(aid) or {}).get(buchstabe) or {}
            nach_modell.setdefault(modell, {})[aid] = eintrag

    ergebnis: dict[str, dict] = {}
    for modell, szenen in nach_modell.items():
        befunde: list[dict] = []
        for aid, eintrag in sorted(szenen.items()):
            text = eintrag.get("text", "")
            kategorie = auftrag_nach_id.get(aid, {}).get("kategorie", aid)
            woerter = len(text.split())

            if eintrag.get("fehler"):
                befunde.append({"szene": aid, "art": "Fehler", "schwere": "hart",
                                "was": eintrag["fehler"]})
                continue
            if woerter < 80:
                befunde.append({"szene": aid, "art": "Zu kurz", "schwere": "hart",
                                "was": f"nur {woerter} Wörter, sehr wahrscheinlich abgebrochen"})

            for t in _treffer(text, VERWEIGERUNG):
                befunde.append({"szene": aid, "art": "Verweigerung", "schwere": "hart",
                                "was": f"Formulierung: {t}"})
            for t in _treffer(text, ABBLENDEN):
                befunde.append({"szene": aid, "art": "Abgeblendet", "schwere": "weich",
                                "was": f"Formulierung: {t}"})
            for t in eintrag.get("banlisten_treffer") or []:
                befunde.append({"szene": aid, "art": "Banliste", "schwere": "weich",
                                "was": t})
            for w in _eigenwiederholung(text):
                befunde.append({"szene": aid, "art": "Wortkreisen", "schwere": "weich",
                                "was": w})

            for regel in pruefregeln:
                if regel.get("szenen") and aid not in regel["szenen"]:
                    continue
                for t in _treffer(text, regel.get("verboten", [])):
                    befunde.append({"szene": aid, "art": "Faktencheck", "schwere": "pruefen",
                                    "was": f"\"{t}\" gefunden, {regel.get('hinweis', '')}"})

            _ = kategorie  # nur zur Lesbarkeit der Rohdaten

        # Wiederholung zwischen je zwei Szenen desselben Modells.
        ids = sorted(szenen)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = szenen[ids[i]].get("text", ""), szenen[ids[j]].get("text", "")
                if not a.strip() or not b.strip():
                    continue
                quote = _ueberlappung(a, b)
                if quote >= 0.12:
                    schwere = "hart" if quote >= 0.20 else "weich"
                    befunde.append({
                        "szene": f"{ids[i]} vs {ids[j]}",
                        "art": "Selbstwiederholung",
                        "schwere": schwere,
                        "was": f"{quote:.0%} der Dreiwortfolgen kommen in beiden Szenen vor",
                    })

        ergebnis[modell] = {
            "befunde": befunde,
            "hart": sum(1 for b in befunde if b["schwere"] == "hart"),
            "weich": sum(1 for b in befunde if b["schwere"] == "weich"),
            "pruefen": sum(1 for b in befunde if b["schwere"] == "pruefen"),
            "woerter_schnitt": round(
                sum(len((e.get("text") or "").split()) for e in szenen.values())
                / max(len(szenen), 1)
            ),
            "sekunden_schnitt": round(
                sum(e.get("sekunden", 0) for e in szenen.values()) / max(len(szenen), 1), 1
            ),
        }
    return ergebnis


def bericht(ergebnis: dict) -> str:
    if not ergebnis:
        return "Keine Daten."
    zeilen = ["", "Grobsieb", "=" * 70, ""]
    zeilen.append(f"{'Modell':<46}{'hart':>6}{'weich':>7}{'prüfen':>8}")
    zeilen.append("-" * 70)
    for modell in sorted(ergebnis, key=lambda m: (ergebnis[m]["hart"], ergebnis[m]["weich"])):
        e = ergebnis[modell]
        zeilen.append(f"{modell[:45]:<46}{e['hart']:>6}{e['weich']:>7}{e['pruefen']:>8}")
    zeilen.append("")
    zeilen.append("hart   = fällt durch, gar nicht erst weiterlesen")
    zeilen.append("weich  = auffällig, im Text nachsehen")
    zeilen.append("prüfen = Stichwort gefunden, kann Fehlalarm sein, selbst beurteilen")
    zeilen.append("")

    for modell in sorted(ergebnis, key=lambda m: (ergebnis[m]["hart"], ergebnis[m]["weich"])):
        e = ergebnis[modell]
        zeilen.append("")
        zeilen.append(modell)
        zeilen.append("-" * len(modell))
        zeilen.append(
            f"  im Schnitt {e['woerter_schnitt']} Wörter, {e['sekunden_schnitt']} s je Szene"
        )
        if not e["befunde"]:
            zeilen.append("  keine Befunde")
            continue
        for b in e["befunde"]:
            marke = {"hart": "!!", "weich": " -", "pruefen": " ?"}[b["schwere"]]
            zeilen.append(f"  {marke} [{b['szene']}] {b['art']}: {b['was']}")
    zeilen.append("")
    return "\n".join(zeilen)
