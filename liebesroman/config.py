"""Konfiguration: Provider, Modelle pro Rolle, Sampler."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Sampler laut Handoff Abschnitt 5.
# top_p und top_k bewusst deaktiviert, min_p übernimmt die Auswahl.
SAMPLER_SCHREIBER = {
    "temperature": 0.9,
    "top_p": 1.0,
    "min_p": 0.05,
    "repetition_penalty": 1.05,
    "max_tokens": 1600,
}

# Hilfsrollen brauchen Genauigkeit, nicht Kreativität.
SAMPLER_ANALYSE = {
    "temperature": 0.2,
    "top_p": 1.0,
    "max_tokens": 1200,
}

# Diese Parameter kennt nicht jeder Endpunkt. Wer sie nicht kennt, antwortet
# mit HTTP 400. Dann werden sie einmalig entfernt und der Call wiederholt.
OPTIONALE_SAMPLER = ("min_p", "repetition_penalty", "top_k", "dry_multiplier")


@dataclass
class Rollenmodell:
    """Ein Modell für eine Rolle. Rollen dürfen sich ein Modell teilen."""

    modell: str
    base_url: str | None = None  # None heißt: globale base_url benutzen
    api_key_env: str = "LR_API_KEY"


@dataclass
class Config:
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_env: str = "LR_API_KEY"

    # Vier Rollen. Zu Beginn dasselbe Modell für alle, unterschieden nur
    # durch den Systemprompt. Getrennt wird die Rolle, nicht die Gewichte.
    schreiber: Rollenmodell = field(
        default_factory=lambda: Rollenmodell("mistralai/mistral-small-3.2-24b-instruct")
    )
    planer: Rollenmodell = field(
        default_factory=lambda: Rollenmodell("mistralai/mistral-small-3.2-24b-instruct")
    )
    pruefer: Rollenmodell = field(
        default_factory=lambda: Rollenmodell("mistralai/mistral-small-3.2-24b-instruct")
    )
    aktenfuehrer: Rollenmodell = field(
        default_factory=lambda: Rollenmodell("mistralai/mistral-small-3.2-24b-instruct")
    )

    # Wie viele Szenen im Wortlaut in den Kontext gehen. Ältere nur als
    # Zusammenfassung.
    szenen_im_wortlaut: int = 2

    # Wie oft eine Szene bei schweren Widersprüchen neu erzeugt wird.
    max_neuversuche: int = 2

    # Mehrfachgenerierung: n Varianten erzeugen, beste per Prüferurteil
    # wählen. 1 heißt aus.
    varianten: int = 1

    zielwoerter: int = 600
    sprache: str = "Deutsch"

    def rolle(self, name: str) -> Rollenmodell:
        rm: Rollenmodell = getattr(self, name)
        return Rollenmodell(
            modell=rm.modell,
            base_url=rm.base_url or self.base_url,
            api_key_env=rm.api_key_env or self.api_key_env,
        )

    @classmethod
    def laden(cls, pfad: Path | None) -> "Config":
        cfg = cls()
        if pfad and pfad.exists():
            roh = json.loads(pfad.read_text(encoding="utf-8"))
            for key, wert in roh.items():
                if key in ("schreiber", "planer", "pruefer", "aktenfuehrer"):
                    setattr(cfg, key, Rollenmodell(**wert))
                elif hasattr(cfg, key):
                    setattr(cfg, key, wert)
        if os.environ.get("LR_BASE_URL"):
            cfg.base_url = os.environ["LR_BASE_URL"]
        return cfg

    def speichern(self, pfad: Path) -> None:
        pfad.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
