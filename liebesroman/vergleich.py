"""Blindvergleich mehrerer Modelle über ein festes Testset.

Der Sinn ist, dass die Bewertung blind passiert. Wer weiß, welches Modell
gerade dran war, bewertet den Namen mit. Die Zuordnung liegt deshalb in einer
zweiten Datei, die man erst nach dem Lesen öffnet.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import requests

from . import bible, prompts
from .config import SAMPLER_SCHREIBER, Config, Rollenmodell
from .llm import Client, LLMFehler
from .pipeline import _banliste_treffer, _prosa_und_protokoll


def modelle_abfragen(base_url: str, suche: str = "") -> list[dict]:
    """Holt die Modellliste vom Endpunkt. Funktioniert bei OpenRouter und vLLM."""
    url = f"{base_url.rstrip('/')}/models"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    daten = r.json().get("data", [])
    treffer = []
    begriffe = [b.lower() for b in suche.split()] if suche else []
    for m in daten:
        mid = m.get("id", "")
        text = (mid + " " + str(m.get("name", "")) + " " + str(m.get("description", ""))).lower()
        if begriffe and not all(b in text for b in begriffe):
            continue
        preis = m.get("pricing") or {}
        treffer.append(
            {
                "id": mid,
                "kontext": m.get("context_length"),
                "preis_ein": preis.get("prompt"),
                "preis_aus": preis.get("completion"),
            }
        )
    return sorted(treffer, key=lambda x: x["id"])


def _preis_pro_million(wert) -> str:
    try:
        return f"{float(wert) * 1_000_000:.2f}"
    except (TypeError, ValueError):
        return "?"


def liste_formatieren(treffer: list[dict]) -> str:
    if not treffer:
        return "Keine Treffer."
    zeilen = [f"{'Modell':<62} {'Kontext':>8} {'Ein':>7} {'Aus':>7}  (USD je Mio. Token)"]
    for t in treffer:
        zeilen.append(
            f"{t['id']:<62} {str(t['kontext'] or '?'):>8} "
            f"{_preis_pro_million(t['preis_ein']):>7} {_preis_pro_million(t['preis_aus']):>7}"
        )
    return "\n".join(zeilen)


def lauf(
    testset_pfad: Path,
    modelle: list[str],
    cfg: Config,
    ziel: Path,
    client: Client,
    nur: list[str] | None = None,
    log=print,
) -> Path:
    testset = json.loads(testset_pfad.read_text(encoding="utf-8"))
    akte = bible.neue_akte(testset["akte"], cfg.sprache)
    for schluessel in ("zeitachse", "verbrauchte_bilder"):
        akte[schluessel] = testset["akte"].get(schluessel, [])
    akte_text = bible.render_kompakt(akte)

    auftraege = testset["auftraege"]
    if nur:
        auftraege = [a for a in auftraege if a["id"] in nur or a["kategorie"] in nur]

    system = prompts.system_schreiber(
        cfg.sprache, prompts.stilbeispiele(), prompts.banliste(cfg.sprache)
    )
    verbotene = prompts.banliste(cfg.sprache)

    # Pro Auftrag eine eigene Zuordnung, damit man nicht nach der ersten Szene
    # weiß, welcher Buchstabe welches Modell ist.
    ergebnisse: dict[str, dict[str, dict]] = {}
    zuordnung: dict[str, dict[str, str]] = {}

    ziel.mkdir(parents=True, exist_ok=True)

    for auftrag in auftraege:
        aid = auftrag["id"]
        ergebnisse[aid] = {}
        gemischt = modelle[:]
        random.shuffle(gemischt)
        zuordnung[aid] = {
            chr(ord("A") + i): modell for i, modell in enumerate(gemischt)
        }
        for buchstabe, modell in zuordnung[aid].items():
            log(f"  {aid} / {buchstabe} ({modell})")
            rm = Rollenmodell(modell=modell, base_url=cfg.base_url, api_key_env=cfg.api_key_env)
            user = prompts.user_schreiber(
                akte_text, "", auftrag["auftrag"], cfg.zielwoerter
            )
            beginn = time.time()
            try:
                antwort = client.chat(rm, system, user, SAMPLER_SCHREIBER, rolle="vergleich")
                text, protokoll = _prosa_und_protokoll(antwort.text)
                fehler = ""
            except LLMFehler as exc:
                text, protokoll, fehler = "", {}, str(exc)
            ergebnisse[aid][buchstabe] = {
                "text": text,
                "protokoll": protokoll,
                "fehler": fehler,
                "sekunden": round(time.time() - beginn, 1),
                "woerter": len(text.split()),
                "banlisten_treffer": _banliste_treffer(text, verbotene),
            }

    blind = ziel / "blind.md"
    blind.write_text(_blindtext(testset, auftraege, ergebnisse), encoding="utf-8")
    (ziel / "zuordnung.json").write_text(
        json.dumps(zuordnung, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ziel / "rohdaten.json").write_text(
        json.dumps(ergebnisse, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ziel / "bewertung.md").write_text(_bogen(auftraege, modelle), encoding="utf-8")
    return blind


def _blindtext(testset: dict, auftraege: list[dict], ergebnisse: dict) -> str:
    teile = [
        "# Blindvergleich",
        "",
        "Die Buchstaben stehen pro Auftrag für ein anderes Modell. Erst lesen und",
        "bewerten, dann zuordnung.json öffnen.",
        "",
    ]
    for auftrag in auftraege:
        aid = auftrag["id"]
        teile.append(f"\n## {aid} ({auftrag['kategorie']})")
        teile.append(f"\nAuftrag: {auftrag['auftrag']['beat']}")
        teile.append(f"\nWorauf achten: {auftrag['prueffrage']}\n")
        for buchstabe in sorted(ergebnisse.get(aid, {})):
            e = ergebnisse[aid][buchstabe]
            teile.append(f"\n### {buchstabe}\n")
            if e["fehler"]:
                teile.append(f"(Fehler: {e['fehler']})")
                continue
            if not e["text"].strip():
                teile.append("(leere Antwort)")
                continue
            teile.append(e["text"])
            hinweise = [f"{e['woerter']} Wörter", f"{e['sekunden']} s"]
            if e["banlisten_treffer"]:
                hinweise.append("Banliste: " + ", ".join(e["banlisten_treffer"]))
            teile.append(f"\n> {' | '.join(hinweise)}")
    return "\n".join(teile) + "\n"


def _bogen(auftraege: list[dict], modelle: list[str]) -> str:
    zeilen = [
        "# Bewertungsbogen",
        "",
        f"Modelle im Lauf ({len(modelle)}): siehe zuordnung.json, erst nach dem Lesen.",
        "",
        "Pro Auftrag und Buchstabe eine Note von 1 bis 5 und einen Satz Begründung.",
        "1 unbrauchbar, 3 veröffentlichbar mit Überarbeitung, 5 würde ich so lesen.",
        "",
    ]
    for a in auftraege:
        zeilen.append(f"## {a['id']} ({a['kategorie']})")
        zeilen.append(f"Worauf achten: {a['prueffrage']}")
        zeilen.append("")
        for buchstabe in [chr(ord("A") + i) for i in range(len(modelle))]:
            zeilen.append(f"- {buchstabe}: Note __  weil ")
        zeilen.append("")
    return "\n".join(zeilen)
