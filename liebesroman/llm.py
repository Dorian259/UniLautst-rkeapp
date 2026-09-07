"""Client für OpenAI-kompatible Chat-Endpunkte, plus ein Mock zum Testen."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

from .config import OPTIONALE_SAMPLER, Rollenmodell


class LLMFehler(RuntimeError):
    pass


@dataclass
class Antwort:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class Verbrauch:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def buchen(self, a: Antwort) -> None:
        self.calls += 1
        self.prompt_tokens += a.prompt_tokens
        self.completion_tokens += a.completion_tokens

    def zeile(self) -> str:
        return (
            f"{self.calls} Calls, {self.prompt_tokens} Prompt-Tokens, "
            f"{self.completion_tokens} Completion-Tokens"
        )


class Client:
    """Ruft einen OpenAI-kompatiblen /chat/completions Endpunkt auf.

    Fällt der Endpunkt über einen unbekannten Sampler-Parameter, werden die
    optionalen Parameter einmalig entfernt und der Call wiederholt. Das hält
    denselben Code für OpenRouter, vLLM und llama.cpp lauffähig.
    """

    def __init__(self, protokoll: Path | None = None, timeout: int = 300):
        self.protokoll = protokoll
        self.timeout = timeout
        self.verbrauch = Verbrauch()
        self._ohne_optionale: set[str] = set()

    def chat(
        self,
        rollenmodell: Rollenmodell,
        system: str,
        user: str,
        sampler: dict,
        rolle: str = "",
    ) -> Antwort:
        key = os.environ.get(rollenmodell.api_key_env or "LR_API_KEY", "")
        if not key:
            raise LLMFehler(
                f"Kein API-Key in {rollenmodell.api_key_env}. "
                f"Siehe .env.example, oder --provider mock zum Trockenlauf."
            )

        payload = {
            "model": rollenmodell.modell,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        for k, v in sampler.items():
            if k in OPTIONALE_SAMPLER and rollenmodell.modell in self._ohne_optionale:
                continue
            payload[k] = v

        url = f"{str(rollenmodell.base_url).rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        letzter_fehler = ""
        for versuch in range(4):
            try:
                r = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
            except requests.RequestException as exc:
                letzter_fehler = str(exc)
                time.sleep(2 ** versuch)
                continue

            if r.status_code == 400 and not (
                rollenmodell.modell in self._ohne_optionale
            ):
                # Sehr wahrscheinlich ein Sampler-Parameter, den der Endpunkt
                # nicht kennt. Einmal ohne die optionalen Parameter versuchen.
                self._ohne_optionale.add(rollenmodell.modell)
                for k in OPTIONALE_SAMPLER:
                    payload.pop(k, None)
                continue

            if r.status_code in (429, 500, 502, 503, 504):
                letzter_fehler = f"HTTP {r.status_code}: {r.text[:300]}"
                time.sleep(2 ** versuch)
                continue

            if r.status_code != 200:
                raise LLMFehler(f"HTTP {r.status_code}: {r.text[:600]}")

            daten = r.json()
            try:
                text = daten["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError) as exc:
                raise LLMFehler(f"Unerwartete Antwortform: {str(daten)[:400]}") from exc

            usage = daten.get("usage") or {}
            antwort = Antwort(
                text=text.strip(),
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
            )
            self.verbrauch.buchen(antwort)
            self._protokollieren(rolle, rollenmodell.modell, system, user, antwort.text)
            return antwort

        raise LLMFehler(f"Endpunkt nach vier Versuchen nicht erreichbar: {letzter_fehler}")

    def _protokollieren(
        self, rolle: str, modell: str, system: str, user: str, ausgabe: str
    ) -> None:
        if not self.protokoll:
            return
        eintrag = {
            "zeit": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rolle": rolle,
            "modell": modell,
            "system": system,
            "user": user,
            "ausgabe": ausgabe,
        }
        with self.protokoll.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


class MockClient(Client):
    """Lässt die Schleife ohne API-Key laufen. Nur für Mechanik-Tests."""

    def chat(self, rollenmodell, system, user, sampler, rolle=""):
        text = _mock_text(rolle)
        antwort = Antwort(text=text, prompt_tokens=len(user) // 4, completion_tokens=len(text) // 4)
        self.verbrauch.buchen(antwort)
        self._protokollieren(rolle, "mock", system, user, text)
        return antwort


def _mock_text(rolle: str) -> str:
    if rolle == "planer":
        return json.dumps(
            {
                "ziel": "Sie bemerkt eine Lücke in seiner Erzählung.",
                "pov": "Lena",
                "ort": "Küche",
                "zeit": "spät abends",
                "beat": "Beiläufiges Gespräch kippt in Misstrauen.",
                "ende": "Sein Handy klingelt, er geht nicht ran.",
            },
            ensure_ascii=False,
        )
    if rolle == "pruefer":
        return json.dumps({"widersprueche": [], "wiederholungen": []}, ensure_ascii=False)
    if rolle == "aktenfuehrer":
        return json.dumps(
            {
                "figuren_neu": [],
                "figuren_updates": [],
                "weltfakten_neu": [],
                "zeitachse_eintrag": "Lena bemerkt die Lücke in seiner Erzählung.",
                "faeden_neu": [],
                "faeden_geschlossen": [],
                "bilder_neu": [],
            },
            ensure_ascii=False,
        )
    return (
        "Platzhalterprosa aus dem Mock-Provider. Der Text ist absichtlich "
        "belanglos, weil hier nur die Mechanik der Schleife geprüft wird.\n\n"
        "---ZUSAMMENFASSUNG---\n"
        + json.dumps(
            {
                "was_passiert": "Lena bemerkt eine Lücke in seiner Erzählung.",
                "anwesend": ["Lena"],
                "ort": "Küche",
                "zeitsprung": "keiner",
                "neue_fakten": [],
                "verwendete_bilder": [],
            },
            ensure_ascii=False,
        )
    )


def json_aus_text(text: str) -> dict:
    """Holt ein JSON-Objekt aus einer Modellantwort.

    Modelle verpacken JSON gern in Codefences oder stellen einen Satz davor.
    Beides wird hier abgeräumt.
    """
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise LLMFehler(f"Kein JSON in der Antwort: {text[:300]}")
    tiefe = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        z = text[i]
        if in_string:
            if escape:
                escape = False
            elif z == "\\":
                escape = True
            elif z == '"':
                in_string = False
            continue
        if z == '"':
            in_string = True
        elif z == "{":
            tiefe += 1
        elif z == "}":
            tiefe -= 1
            if tiefe == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as exc:
                    raise LLMFehler(f"Kaputtes JSON: {text[start:i+1][:300]}") from exc
    raise LLMFehler(f"Unvollständiges JSON: {text[start:start+300]}")
