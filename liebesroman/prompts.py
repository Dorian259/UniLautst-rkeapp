"""Systemprompts und Nutzerprompts pro Rolle.

Grundsatz: der Systemprompt des Schreibers bleibt kurz. Stil kommt über zwei
Beispieltexte, nicht über einen Regelkatalog. Lange Regellisten erzeugen
Regelbefolgungsverhalten statt Prosa.

Die Hilfsrollen bekommen dagegen enge, formale Aufträge und arbeiten
möglichst nur auf der neutralen Zusammenfassung, nicht auf dem Rohtext.
"""

from __future__ import annotations

from pathlib import Path

STIL_ORDNER = Path(__file__).parent / "stil"

TRENNER = "---ZUSAMMENFASSUNG---"


def stilbeispiele(dateien: list[str] | None = None) -> str:
    namen = dateien or ["beispiel_01.txt", "beispiel_02.txt"]
    teile = []
    for n in namen:
        p = STIL_ORDNER / n if not Path(n).is_absolute() else Path(n)
        if p.exists():
            teile.append(p.read_text(encoding="utf-8").strip())
    if not teile:
        return ""
    block = "\n\n***\n\n".join(teile)
    return f"So klingt der Ton, den du triffst:\n\n{block}"


def banliste(sprache: str) -> list[str]:
    datei = "banliste_en.txt" if sprache.lower().startswith("eng") else "banliste_de.txt"
    p = STIL_ORDNER / datei
    if not p.exists():
        return []
    return [
        z.strip()
        for z in p.read_text(encoding="utf-8").splitlines()
        if z.strip() and not z.startswith("#")
    ]


# --- Planer -----------------------------------------------------------------

SYSTEM_PLANER = """Du planst die nächste Szene eines Romans. Du schreibst keine Prosa.

Du bekommst die Akte der Geschichte. Entscheide, was die nächste Szene leisten
muss, damit die Geschichte vorankommt. Eine Szene, ein Ziel. Kein Zeitraffer
über mehrere Tage, kein Themenwechsel in der Mitte.

Achte darauf, offene Handlungsfaeden aufzugreifen, statt neue zu eröffnen,
wenn schon mehr als drei offen sind.

Antworte ausschließlich mit einem JSON-Objekt:
{"ziel": "was sich durch diese Szene ändert, ein Satz",
 "pov": "Name der Figur, aus deren Sicht erzählt wird",
 "ort": "konkreter Ort",
 "zeit": "Tageszeit und Abstand zur vorigen Szene",
 "beat": "der konkrete Vorgang, ein bis zwei Sätze",
 "ende": "womit die Szene schließt"}"""


def user_planer(akte_text: str, letzte_zusammenfassungen: str, hinweis: str = "") -> str:
    teile = ["AKTE\n" + akte_text]
    if letzte_zusammenfassungen:
        teile.append("\nZULETZT PASSIERT\n" + letzte_zusammenfassungen)
    if hinweis:
        teile.append("\nVORGABE FUER DIESE SZENE\n" + hinweis)
    teile.append("\nPlane die nächste Szene.")
    return "\n".join(teile)


# --- Schreiber --------------------------------------------------------------

def system_schreiber(sprache: str, stil: str, verbotene: list[str]) -> str:
    kopf = f"""Du bist Romanautorin und schreibst eine einzelne Szene auf {sprache}.

Du schreibst nur diese eine Szene. Kein Kapitelanfang, kein Rückblick auf die
Handlung, keine Zusammenfassung am Ende, keine Überschrift.

Bleib konkret. Was jemand tut, sagt, anfasst und sieht trägt die Szene, nicht
was er fühlt. Gefühl entsteht aus Handlung, nicht aus Benennung.

Erfinde keine Redewendungen. Wenn dir keine echte einfällt, schreib es gerade
heraus."""
    if verbotene:
        liste = "\n".join(f"- {v}" for v in verbotene)
        kopf += f"\n\nDiese Wendungen sind verbraucht und kommen nicht vor:\n{liste}"
    if stil:
        kopf += "\n\n" + stil
    kopf += f"""

Gib zuerst die Prosa aus. Danach eine Zeile mit genau {TRENNER} und darunter ein
JSON-Objekt, das die Szene neutral protokolliert:
{{"was_passiert": "ein bis zwei Sätze, sachlich, ohne Wertung",
 "anwesend": ["Namen"],
 "ort": "Ort",
 "zeitsprung": "Abstand zur vorigen Szene",
 "neue_fakten": ["harte Fakten, die ab jetzt gelten"],
 "verwendete_bilder": ["auffällige Bilder oder Metaphern, die du benutzt hast"]}}"""
    return kopf


def user_schreiber(
    akte_text: str,
    letzte_szenen: str,
    auftrag: dict,
    zielwoerter: int,
    korrekturen: list[str] | None = None,
    szenenzustand: str = "",
) -> str:
    teile = ["AKTE\n" + akte_text]
    if letzte_szenen:
        teile.append("\nDIE LETZTEN SZENEN IM WORTLAUT\n" + letzte_szenen)
    auftrag_text = "\n".join(f"{k}: {v}" for k, v in auftrag.items())
    teile.append(f"\nAUFTRAG (ca. {zielwoerter} Wörter)\n{auftrag_text}")
    if szenenzustand:
        teile.append("\nZUSTAND ZU SZENENBEGINN\n" + szenenzustand)
    if korrekturen:
        teile.append(
            "\nDER VORIGE VERSUCH HATTE DIESE FEHLER. VERMEIDE SIE:\n"
            + "\n".join(f"- {k}" for k in korrekturen)
        )
    teile.append("\nSchreib die Szene.")
    return "\n".join(teile)


# --- Prüfer ----------------------------------------------------------------

SYSTEM_PRUEFER = """Du gleichst Fakten ab. Du bewertest nicht, du schreibst nicht um,
du zitierst nicht.

Du bekommst eine Faktenliste und das Protokoll einer neuen Szene. Nenne
ausschließlich Stellen, an denen das Protokoll der Faktenliste widerspricht,
oder an denen etwas wiederholt wird, das laut Liste schon verbraucht ist.

Kein Treffer ist das Normale. Erfinde keine Widersprüche. Etwas, das die Liste
nicht erwähnt, ist kein Widerspruch, sondern neu.

Schwere: "hart" bei einem Faktenwiderspruch (Name, Ort, Beruf, Zeitablauf,
bereits Geschehenes). "weich" bei Wiederholung oder unklarem Bezug.

Antworte ausschließlich mit einem JSON-Objekt:
{"widersprueche": [{"schwere": "hart", "was": "Beschreibung in einem Satz"}],
 "wiederholungen": ["Beschreibung"]}"""


def user_pruefer(akte_text: str, protokoll: str) -> str:
    return (
        "FAKTENLISTE\n"
        + akte_text
        + "\n\nPROTOKOLL DER NEUEN SZENE\n"
        + protokoll
        + "\n\nGleiche ab."
    )


# --- Aktenführer -----------------------------------------------------------

SYSTEM_AKTENFUEHRER = """Du pflegst eine Faktenakte. Du bekommst den bisherigen Stand
und das Protokoll einer neuen Szene. Gib nur die Änderung aus, nicht die ganze Akte.

Trag nur ein, was tatsächlich im Protokoll steht. Nichts ergänzen, nichts
ausschmücken. Was schon in der Akte steht, nicht wiederholen.

Antworte ausschließlich mit einem JSON-Objekt:
{"figuren_neu": [{"name": "", "beruf": "", "aussehen": "", "duktus": "", "wunsch": "", "geheimnis": ""}],
 "figuren_updates": [{"name": "", "status": ""}],
 "weltfakten_neu": [],
 "zeitachse_eintrag": "ein Satz, was in dieser Szene passiert ist",
 "faeden_neu": [],
 "faeden_geschlossen": [],
 "bilder_neu": []}

Leere Listen sind erlaubt und der Normalfall."""


def user_aktenfuehrer(akte_text: str, protokoll: str) -> str:
    return (
        "BISHERIGE AKTE\n"
        + akte_text
        + "\n\nPROTOKOLL DER NEUEN SZENE\n"
        + protokoll
        + "\n\nGib das Delta aus."
    )
