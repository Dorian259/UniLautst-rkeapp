"""Die Szenenschleife: Planer, Schreiber, Prüfer, Aktenführer."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import bible, prompts
from .config import SAMPLER_ANALYSE, SAMPLER_SCHREIBER, Config
from .llm import Client, LLMFehler, json_aus_text


@dataclass
class Szene:
    nr: int
    auftrag: dict
    text: str
    protokoll: dict
    befunde: list[str] = field(default_factory=list)
    versuche: int = 1

    def als_dict(self) -> dict:
        return {
            "nr": self.nr,
            "auftrag": self.auftrag,
            "protokoll": self.protokoll,
            "befunde": self.befunde,
            "versuche": self.versuche,
            "woerter": len(self.text.split()),
        }


class Geschichte:
    """Ein Verzeichnis unter stories/ mit Akte, Szenentexten und Protokoll."""

    def __init__(self, ordner: Path, cfg: Config, client: Client):
        self.ordner = ordner
        self.cfg = cfg
        self.client = client
        self.szenen_ordner = ordner / "szenen"

    # --- Persistenz ---------------------------------------------------------

    @property
    def akte_pfad(self) -> Path:
        return self.ordner / "akte.json"

    @property
    def index_pfad(self) -> Path:
        return self.ordner / "szenen.json"

    def akte(self) -> dict:
        return bible.laden(self.akte_pfad)

    def index(self) -> list[dict]:
        if not self.index_pfad.exists():
            return []
        return json.loads(self.index_pfad.read_text(encoding="utf-8"))

    def szenentext(self, nr: int) -> str:
        p = self.szenen_ordner / f"{nr:04d}.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def anlegen(self, vorgaben: dict) -> None:
        self.ordner.mkdir(parents=True, exist_ok=True)
        self.szenen_ordner.mkdir(exist_ok=True)
        akte = bible.neue_akte(vorgaben, self.cfg.sprache)
        bible.speichern(akte, self.akte_pfad)
        self.index_pfad.write_text("[]", encoding="utf-8")

    # --- Kontextaufbau ------------------------------------------------------

    def _letzte_szenen_wortlaut(self) -> str:
        idx = self.index()
        if not idx:
            return ""
        nummern = [e["nr"] for e in idx[-self.cfg.szenen_im_wortlaut :]]
        teile = [f"[Szene {n}]\n{self.szenentext(n)}" for n in nummern]
        return "\n\n".join(t for t in teile if t.strip())

    def _letzte_protokolle(self, anzahl: int = 5) -> str:
        idx = self.index()[-anzahl:]
        zeilen = []
        for e in idx:
            p = e.get("protokoll") or {}
            zeilen.append(f"Szene {e['nr']}: {p.get('was_passiert', '')}")
        return "\n".join(zeilen)

    # --- Die vier Rollen ----------------------------------------------------

    def planen(self, akte_text: str, hinweis: str = "") -> dict:
        antwort = self.client.chat(
            self.cfg.rolle("planer"),
            prompts.SYSTEM_PLANER,
            prompts.user_planer(akte_text, self._letzte_protokolle(), hinweis),
            SAMPLER_ANALYSE,
            rolle="planer",
        )
        return json_aus_text(antwort.text)

    def schreiben(
        self, akte_text: str, auftrag: dict, korrekturen: list[str] | None = None
    ) -> tuple[str, dict]:
        system = prompts.system_schreiber(
            self.cfg.sprache,
            prompts.stilbeispiele(),
            prompts.banliste(self.cfg.sprache),
        )
        user = prompts.user_schreiber(
            akte_text,
            self._letzte_szenen_wortlaut(),
            auftrag,
            self.cfg.zielwoerter,
            korrekturen,
        )
        antwort = self.client.chat(
            self.cfg.rolle("schreiber"), system, user, SAMPLER_SCHREIBER, rolle="schreiber"
        )
        return _prosa_und_protokoll(antwort.text)

    def pruefen(self, akte_text: str, protokoll: dict) -> dict:
        antwort = self.client.chat(
            self.cfg.rolle("pruefer"),
            prompts.SYSTEM_PRUEFER,
            prompts.user_pruefer(akte_text, json.dumps(protokoll, ensure_ascii=False, indent=2)),
            SAMPLER_ANALYSE,
            rolle="pruefer",
        )
        return json_aus_text(antwort.text)

    def akte_fortschreiben(self, akte: dict, protokoll: dict) -> list[str]:
        antwort = self.client.chat(
            self.cfg.rolle("aktenfuehrer"),
            prompts.SYSTEM_AKTENFUEHRER,
            prompts.user_aktenfuehrer(
                bible.render_kompakt(akte),
                json.dumps(protokoll, ensure_ascii=False, indent=2),
            ),
            SAMPLER_ANALYSE,
            rolle="aktenfuehrer",
        )
        delta = json_aus_text(antwort.text)
        return bible.delta_anwenden(akte, delta)

    # --- Die Schleife -------------------------------------------------------

    def nächste_szene(self, hinweis: str = "", log=print) -> Szene:
        akte = self.akte()
        akte_text = bible.render_kompakt(akte)
        nr = akte["meta"]["szenen_gesamt"] + 1

        auftrag = self.planen(akte_text, hinweis)
        log(f"  Plan: {auftrag.get('ziel', '?')}")

        verbotene = prompts.banliste(self.cfg.sprache)
        korrekturen: list[str] = []
        text = ""
        protokoll: dict = {}
        befunde: list[str] = []

        for versuch in range(1, self.cfg.max_neuversuche + 2):
            text, protokoll = self.schreiben(akte_text, auftrag, korrekturen or None)

            befunde = []
            for treffer in _banliste_treffer(text, verbotene):
                befunde.append(f"verbrauchte Wendung: {treffer}")

            urteil = self.pruefen(akte_text, protokoll)
            harte = [
                w.get("was", str(w))
                for w in (urteil.get("widersprueche") or [])
                if isinstance(w, dict) and w.get("schwere") == "hart"
            ]
            weiche = [
                w.get("was", str(w))
                for w in (urteil.get("widersprueche") or [])
                if not (isinstance(w, dict) and w.get("schwere") == "hart")
            ]
            befunde += [f"Widerspruch: {h}" for h in harte]
            befunde += [f"weich: {w}" for w in weiche]
            befunde += [f"Wiederholung: {w}" for w in (urteil.get("wiederholungen") or [])]

            blocker = harte + _banliste_treffer(text, verbotene)
            if not blocker or versuch > self.cfg.max_neuversuche:
                if blocker:
                    log(f"  Neuversuche aufgebraucht, Szene wird übernommen: {blocker}")
                break

            log(f"  Neuversuch {versuch}: {blocker}")
            korrekturen = blocker

        # Szene festschreiben
        self.szenen_ordner.mkdir(parents=True, exist_ok=True)
        (self.szenen_ordner / f"{nr:04d}.md").write_text(text, encoding="utf-8")

        notizen = self.akte_fortschreiben(akte, protokoll)
        akte["meta"]["szenen_gesamt"] = nr
        bible.speichern(akte, self.akte_pfad)

        szene = Szene(nr=nr, auftrag=auftrag, text=text, protokoll=protokoll, befunde=befunde)
        idx = self.index()
        idx.append(szene.als_dict())
        self.index_pfad.write_text(
            json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for n in notizen:
            log(f"  Akte: {n}")
        return szene

    def gesamttext(self) -> str:
        teile = []
        for e in self.index():
            teile.append(self.szenentext(e["nr"]).strip())
        return "\n\n* * *\n\n".join(t for t in teile if t)


def _prosa_und_protokoll(rohtext: str) -> tuple[str, dict]:
    """Trennt Prosa und Protokoll. Fehlt das Protokoll, bleibt es leer."""
    if prompts.TRENNER in rohtext:
        prosa, rest = rohtext.split(prompts.TRENNER, 1)
        try:
            return prosa.strip(), json_aus_text(rest)
        except LLMFehler:
            return prosa.strip(), {}
    # Manche Modelle lassen den Trenner weg und hängen nur das JSON an.
    pos = rohtext.rfind("{")
    if pos > 0:
        try:
            return rohtext[:pos].strip(), json_aus_text(rohtext[pos:])
        except LLMFehler:
            pass
    return rohtext.strip(), {}


def _banliste_treffer(text: str, verbotene: list[str]) -> list[str]:
    from .sieben import normal

    klein = normal(text)
    treffer = []
    for v in verbotene:
        # Toleriert Zeilenumbrueche innerhalb der Wendung, aber keine
        # Teilwort-Zufallstreffer.
        muster = re.escape(normal(v)).replace(r"\ ", r"\s+")
        if re.search(muster, klein):
            treffer.append(v)
    return treffer
