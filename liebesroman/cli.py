"""Kommandozeile: init, weiter, lesen, akte, kosten."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bible
from .config import Config
from .llm import Client, LLMFehler, MockClient
from .pipeline import Geschichte
from . import vergleich as vgl
from . import lesepaket as lp
from . import sieben as sb

WURZEL = Path(__file__).resolve().parent.parent
STORIES = WURZEL / "stories"


def _ausgabe_utf8() -> None:
    """Erzwingt UTF-8 auf der Konsole.

    Die Windows-Eingabeaufforderung läuft je nach Einstellung mit einer
    Codepage, die keine Umlaute kann. Jede Ausgabe würde dann mit einem
    UnicodeEncodeError abbrechen, mitten im Lauf.
    """
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _env_laden() -> None:
    """Liest eine .env im Projektwurzelverzeichnis, ohne Zusatzabhängigkeit."""
    import os

    p = WURZEL / ".env"
    if not p.exists():
        return
    # utf-8-sig, weil der Windows-Editor eine Stückliste voranstellt und der
    # erste Variablenname sonst unlesbar wird.
    for zeile in p.read_text(encoding="utf-8-sig").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        k, v = zeile.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _geschichte(name: str, args) -> Geschichte:
    ordner = STORIES / name
    cfg = Config.laden(ordner / "config.json")
    if getattr(args, "modell", None):
        for rolle in ("schreiber", "planer", "pruefer", "aktenfuehrer"):
            getattr(cfg, rolle).modell = args.modell
    if getattr(args, "schreibmodell", None):
        cfg.schreiber.modell = args.schreibmodell
    if getattr(args, "sprache", None):
        cfg.sprache = args.sprache
    if getattr(args, "woerter", None):
        cfg.zielwoerter = args.woerter

    protokoll = ordner / "calls.jsonl"
    client = MockClient(protokoll) if args.provider == "mock" else Client(protokoll)
    return Geschichte(ordner, cfg, client)


def cmd_init(args) -> int:
    ordner = STORIES / args.name
    if ordner.exists() and not args.ersetzen:
        print(f"stories/{args.name} existiert schon. --ersetzen erzwingt neu.")
        return 1
    vorlage = Path(args.vorlage)
    if not vorlage.exists():
        vorlage = WURZEL / args.vorlage
    if not vorlage.exists():
        print(f"Vorlage nicht gefunden: {args.vorlage}")
        return 1

    vorgaben = json.loads(vorlage.read_text(encoding="utf-8"))
    g = _geschichte(args.name, args)
    g.anlegen(vorgaben)
    g.cfg.speichern(ordner / "config.json")
    print(f"Angelegt: stories/{args.name}")
    print(f"Modell Schreiber: {g.cfg.schreiber.modell}")
    print(f"Sprache: {g.cfg.sprache}, Zielwörter pro Szene: {g.cfg.zielwoerter}")
    return 0


def cmd_weiter(args) -> int:
    g = _geschichte(args.name, args)
    if not g.akte_pfad.exists():
        print(f"stories/{args.name} gibt es nicht. Erst 'init'.")
        return 1
    for i in range(args.anzahl):
        nr = g.akte()["meta"]["szenen_gesamt"] + 1
        print(f"\nSzene {nr}")
        try:
            szene = g.nächste_szene(hinweis=args.hinweis if i == 0 else "")
        except LLMFehler as exc:
            print(f"Abbruch: {exc}")
            return 2
        woerter = len(szene.text.split())
        print(f"  Geschrieben: {woerter} Wörter")
        if szene.befunde:
            for b in szene.befunde:
                print(f"  Befund: {b}")
    print(f"\nVerbrauch: {g.client.verbrauch.zeile()}")
    return 0


def cmd_lesen(args) -> int:
    g = _geschichte(args.name, args)
    text = g.gesamttext()
    if args.datei:
        Path(args.datei).write_text(text, encoding="utf-8")
        print(f"Geschrieben: {args.datei} ({len(text.split())} Wörter)")
    else:
        print(text)
    return 0


def cmd_akte(args) -> int:
    g = _geschichte(args.name, args)
    print(bible.render_kompakt(g.akte()))
    return 0


def cmd_status(args) -> int:
    g = _geschichte(args.name, args)
    idx = g.index()
    gesamt = sum(e.get("woerter", 0) for e in idx)
    print(f"Szenen: {len(idx)}, Wörter: {gesamt}")
    for e in idx:
        befunde = e.get("befunde") or []
        marker = f"  [{len(befunde)} Befunde]" if befunde else ""
        print(f"  {e['nr']:>3}. {(e.get('protokoll') or {}).get('was_passiert', '')}{marker}")
    return 0



def cmd_modelle(args) -> int:
    cfg = Config.laden(None)
    treffer = vgl.modelle_abfragen(cfg.base_url, args.suche)
    print(vgl.liste_formatieren(treffer))
    print(f"\n{len(treffer)} Treffer bei {cfg.base_url}")
    return 0


def cmd_vergleich(args) -> int:
    cfg = Config.laden(None)
    if args.sprache:
        cfg.sprache = args.sprache
    if args.woerter:
        cfg.zielwoerter = args.woerter
    ziel = WURZEL / "vergleiche" / args.name
    protokoll = ziel / "calls.jsonl"
    ziel.mkdir(parents=True, exist_ok=True)
    client = MockClient(protokoll) if args.provider == "mock" else Client(protokoll)

    testset = Path(args.testset)
    if not testset.exists():
        testset = WURZEL / args.testset
    if not testset.exists():
        print(f"Testset nicht gefunden: {args.testset}")
        return 1

    print(f"Lauf {args.name}: {len(args.modelle)} Modelle")
    try:
        blind = vgl.lauf(
            testset, args.modelle, cfg, ziel, client, nur=args.nur or None
        )
    except LLMFehler as exc:
        print(f"Abbruch: {exc}")
        return 2
    print(f"\nVerbrauch: {client.verbrauch.zeile()}")
    print(f"Blind lesen: {blind}")
    print(f"Bewerten in: {ziel / 'bewertung.md'}")
    print(f"Erst danach:  {ziel / 'zuordnung.json'}")
    return 0



def cmd_lesepaket(args) -> int:
    lauf = WURZEL / "vergleiche" / args.lauf
    if not (lauf / "rohdaten.json").exists():
        print(f"Kein Lauf unter vergleiche/{args.lauf}. Erst 'vergleich' starten.")
        return 1
    testset = Path(args.testset)
    if not testset.exists():
        testset = WURZEL / args.testset
    if not testset.exists():
        print(f"Testset nicht gefunden: {args.testset}")
        return 1

    ziel = Path(args.datei) if args.datei else lauf / "leseprobe.html"
    seite, schluessel = lp.bauen(lauf, testset, args.modelle, ziel, titel=args.titel)
    print(f"Leseprobe: {seite}")
    print(f"Schlüssel: {schluessel}  (nicht mitschicken)")
    print()
    print("Die HTML-Datei ist eigenständig und braucht kein Internet. Verschicken")
    print("per Mail oder AirDrop, im Browser öffnen, lesen, am Ende auf den Knopf.")
    return 0



def cmd_sieben(args) -> int:
    lauf = WURZEL / "vergleiche" / args.lauf
    if not (lauf / "rohdaten.json").exists():
        print(f"Kein Lauf unter vergleiche/{args.lauf}. Erst 'vergleich' starten.")
        return 1
    testset = Path(args.testset)
    if not testset.exists():
        testset = WURZEL / args.testset
    if not testset.exists():
        print(f"Testset nicht gefunden: {args.testset}")
        return 1

    ergebnis = sb.auswerten(lauf, testset)
    text = sb.bericht(ergebnis)
    print(text)
    (lauf / "grobsieb.txt").write_text(text, encoding="utf-8")
    (lauf / "grobsieb.json").write_text(
        json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Auch gespeichert unter {lauf / 'grobsieb.txt'}")
    return 0


def main(argv=None) -> int:
    _ausgabe_utf8()
    _env_laden()
    p = argparse.ArgumentParser(prog="liebesroman", description=__doc__)
    p.add_argument("--provider", choices=["api", "mock"], default="api",
                   help="mock lässt die Schleife ohne API-Key laufen")
    p.add_argument("--modell", help="setzt das Modell für alle vier Rollen")
    p.add_argument("--schreibmodell", help="setzt nur das Modell des Schreibers")
    p.add_argument("--sprache")
    p.add_argument("--woerter", type=int, help="Zielwörter pro Szene")

    sub = p.add_subparsers(dest="befehl", required=True)

    s = sub.add_parser("init", help="neue Geschichte anlegen")
    s.add_argument("name")
    s.add_argument("--vorlage", default="vorlagen/beispiel.json")
    s.add_argument("--ersetzen", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("weiter", help="nächste Szenen erzeugen")
    s.add_argument("name")
    s.add_argument("-n", "--anzahl", type=int, default=1)
    s.add_argument("--hinweis", default="", help="Vorgabe für die nächste Szene")
    s.set_defaults(func=cmd_weiter)

    s = sub.add_parser("lesen", help="Gesamttext ausgeben")
    s.add_argument("name")
    s.add_argument("--datei")
    s.set_defaults(func=cmd_lesen)

    s = sub.add_parser("akte", help="Akte anzeigen")
    s.add_argument("name")
    s.set_defaults(func=cmd_akte)

    s = sub.add_parser("status", help="Szenenübersicht")
    s.add_argument("name")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("modelle", help="Modellliste des Endpunkts abfragen")
    s.add_argument("suche", nargs="?", default="", help="Filterbegriffe, alle müssen vorkommen")
    s.set_defaults(func=cmd_modelle)

    s = sub.add_parser("vergleich", help="Testset blind über mehrere Modelle laufen lassen")
    s.add_argument("name", help="Name des Laufs, landet unter vergleiche/")
    s.add_argument("modelle", nargs="+", help="Modell-IDs")
    s.add_argument("--testset", default="testset/basis.json")
    s.add_argument("--nur", nargs="*", help="nur diese Auftrags-IDs oder Kategorien")
    s.set_defaults(func=cmd_vergleich)

    s = sub.add_parser("lesepaket", help="Leseprobe für Testleserinnen aus einem Lauf bauen")
    s.add_argument("lauf", help="Name eines Laufs unter vergleiche/")
    s.add_argument("modelle", nargs="+", help="die Modelle, die ins Paket sollen")
    s.add_argument("--testset", default="testset/leseprobe.json")
    s.add_argument("--datei", help="Zieldatei, sonst vergleiche/<lauf>/leseprobe.html")
    s.add_argument("--titel", default="Leseprobe")
    s.set_defaults(func=cmd_lesepaket)

    s = sub.add_parser("sieben", help="einen Lauf automatisch vorauswerten")
    s.add_argument("lauf", help="Name eines Laufs unter vergleiche/")
    s.add_argument("--testset", default="testset/spicy.json")
    s.set_defaults(func=cmd_sieben)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
