"""Die Akte: strukturierter Zustand einer Geschichte, plus kompakte Darstellung.

Der Sinn der Akte ist, dass sie kurz bleibt. Sie geht bei jedem Call vollständig
in den Kontext, während der Gesamttext das irgendwann nicht mehr kann. Alles,
was hier wächst statt ersetzt zu werden, wird gedeckelt.
"""

from __future__ import annotations

import json
from pathlib import Path

# Deckel gegen unbegrenztes Wachstum der Akte.
MAX_ZEITACHSE = 40
MAX_BILDER = 60
MAX_WELTFAKTEN = 40


def neue_akte(vorgaben: dict, sprache: str = "Deutsch") -> dict:
    return {
        "meta": {"sprache": sprache, "szenen_gesamt": 0},
        "vorgaben": {
            "tropes": vorgaben.get("tropes", []),
            "setting": vorgaben.get("setting", ""),
            "intensitaet": vorgaben.get("intensitaet", "romantisch, nicht explizit"),
            "wunschtext": vorgaben.get("wunschtext", ""),
            "leserin": vorgaben.get("leserin", ""),
            "praemisse": vorgaben.get("praemisse", ""),
        },
        "figuren": vorgaben.get("figuren", []),
        "beziehungen": vorgaben.get("beziehungen", []),
        "weltfakten": vorgaben.get("weltfakten", []),
        "zeitachse": [],
        "offene_faeden": vorgaben.get("offene_faeden", []),
        "verbrauchte_bilder": [],
    }


def _liste(werte, aufzaehlung: str = "- ") -> str:
    if not werte:
        return "  (noch nichts)"
    return "\n".join(f"  {aufzaehlung}{w}" for w in werte)


def render_kompakt(akte: dict) -> str:
    """Die Akte als Text für den Prompt. Kürzer und lesbarer als rohes JSON."""
    v = akte["vorgaben"]
    teile: list[str] = []

    teile.append("VORGABEN DER LESERIN")
    if v.get("praemisse"):
        teile.append(f"  Prämisse: {v['praemisse']}")
    if v.get("setting"):
        teile.append(f"  Setting: {v['setting']}")
    if v.get("tropes"):
        teile.append(f"  Tropes: {', '.join(v['tropes'])}")
    teile.append(f"  Intensität: {v.get('intensitaet', '')}")
    if v.get("wunschtext"):
        teile.append(f"  Freier Wunsch: {v['wunschtext']}")
    if v.get("leserin"):
        teile.append(f"  Über die Leserin: {v['leserin']}")

    teile.append("\nFIGUREN")
    if not akte["figuren"]:
        teile.append("  (noch keine)")
    for f in akte["figuren"]:
        zeile = f"  {f.get('name', '?')}"
        details = []
        for schluessel in ("alter", "beruf", "aussehen", "duktus", "wunsch", "geheimnis", "status"):
            if f.get(schluessel):
                details.append(f"{schluessel}: {f[schluessel]}")
        if details:
            zeile += " | " + " | ".join(details)
        teile.append(zeile)

    if akte["beziehungen"]:
        teile.append("\nBEZIEHUNGEN")
        for b in akte["beziehungen"]:
            teile.append(
                f"  {b.get('von', '?')} zu {b.get('zu', '?')}: "
                f"{b.get('art', '')} {b.get('spannung', '')}".rstrip()
            )

    teile.append("\nFESTE WELTFAKTEN (dürfen nicht abweichen)")
    teile.append(_liste(akte["weltfakten"]))

    teile.append("\nBISHERIGE EREIGNISSE (älteste zuerst)")
    if not akte["zeitachse"]:
        teile.append("  (die Geschichte beginnt)")
    for i, e in enumerate(akte["zeitachse"], start=1):
        teile.append(f"  {i}. {e}")

    teile.append("\nOFFENE HANDLUNGSFÄDEN")
    teile.append(_liste([f.get("beschreibung", str(f)) if isinstance(f, dict) else f for f in akte["offene_faeden"]]))

    teile.append("\nBEREITS VERBRAUCHTE BILDER UND METAPHERN (nicht wiederverwenden)")
    teile.append(_liste(akte["verbrauchte_bilder"]))

    return "\n".join(teile)


def delta_anwenden(akte: dict, delta: dict) -> list[str]:
    """Trägt das Delta des Aktenführers ein. Gibt eine Liste der Änderungen zurück."""
    notizen: list[str] = []

    for f in delta.get("figuren_neu") or []:
        if not isinstance(f, dict) or not f.get("name"):
            continue
        if any(x.get("name") == f["name"] for x in akte["figuren"]):
            continue
        akte["figuren"].append(f)
        notizen.append(f"Figur neu: {f['name']}")

    for u in delta.get("figuren_updates") or []:
        if not isinstance(u, dict) or not u.get("name"):
            continue
        for f in akte["figuren"]:
            if f.get("name") == u["name"]:
                for k, w in u.items():
                    if k != "name" and w:
                        f[k] = w
                notizen.append(f"Figur aktualisiert: {u['name']}")
                break

    for fakt in delta.get("weltfakten_neu") or []:
        if fakt and fakt not in akte["weltfakten"]:
            akte["weltfakten"].append(fakt)
            notizen.append(f"Weltfakt: {fakt}")
    akte["weltfakten"] = akte["weltfakten"][-MAX_WELTFAKTEN:]

    eintrag = delta.get("zeitachse_eintrag")
    if eintrag:
        akte["zeitachse"].append(eintrag)
        akte["zeitachse"] = akte["zeitachse"][-MAX_ZEITACHSE:]

    for fa in delta.get("faeden_neu") or []:
        beschreibung = fa.get("beschreibung") if isinstance(fa, dict) else fa
        if beschreibung and not _faden_vorhanden(akte, beschreibung):
            akte["offene_faeden"].append({"beschreibung": beschreibung})
            notizen.append(f"Faden offen: {beschreibung}")

    for zu in delta.get("faeden_geschlossen") or []:
        vorher = len(akte["offene_faeden"])
        akte["offene_faeden"] = [
            f for f in akte["offene_faeden"] if not _passt(f, zu)
        ]
        if len(akte["offene_faeden"]) < vorher:
            notizen.append(f"Faden geschlossen: {zu}")

    for bild in delta.get("bilder_neu") or []:
        if bild and bild not in akte["verbrauchte_bilder"]:
            akte["verbrauchte_bilder"].append(bild)
    akte["verbrauchte_bilder"] = akte["verbrauchte_bilder"][-MAX_BILDER:]

    return notizen


def _faden_text(f) -> str:
    return (f.get("beschreibung", "") if isinstance(f, dict) else str(f)).strip().lower()


def _faden_vorhanden(akte: dict, beschreibung: str) -> bool:
    return any(_faden_text(f) == beschreibung.strip().lower() for f in akte["offene_faeden"])


def _passt(faden, zu: str) -> bool:
    a, b = _faden_text(faden), str(zu).strip().lower()
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def laden(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def speichern(akte: dict, pfad: Path) -> None:
    pfad.write_text(json.dumps(akte, ensure_ascii=False, indent=2), encoding="utf-8")
