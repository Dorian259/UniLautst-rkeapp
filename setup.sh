#!/usr/bin/env bash
# Einmalige Einrichtung auf dem eigenen Rechner.
# Aufruf: bash setup.sh
set -u

cd "$(dirname "$0")" || exit 1
echo "Einrichtung der Liebesroman-Pipeline"
echo

# 1. Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "FEHLER: python3 nicht gefunden."
    echo "Auf dem Mac installieren mit:  brew install python3"
    echo "Falls Homebrew fehlt, siehe https://brew.sh"
    exit 1
fi
echo "Python gefunden: $(python3 --version)"

# 2. Eigene Umgebung, damit nichts am System-Python hängt.
#    Auf neueren macOS-Versionen verweigert pip die Installation ohne venv.
if [ ! -d ".venv" ]; then
    echo "Lege eine eigene Python-Umgebung an (.venv) ..."
    python3 -m venv .venv || { echo "FEHLER beim Anlegen der Umgebung."; exit 1; }
fi
# shellcheck disable=SC1091
. .venv/bin/activate

echo "Installiere Abhängigkeiten ..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt || { echo "FEHLER bei pip install."; exit 1; }
echo "Abhängigkeiten installiert."
echo

# 3. Schlüssel
if [ -f ".env" ] && grep -q "^LR_API_KEY=sk-" .env 2>/dev/null; then
    echo "Es gibt schon eine .env mit einem Schlüssel."
    printf "Überschreiben? [j/N] "
    read -r antwort
    if [ "$antwort" != "j" ] && [ "$antwort" != "J" ]; then
        schluessel=""
    fi
fi

if [ ! -f ".env" ] || [ "${antwort:-j}" = "j" ] || [ "${antwort:-j}" = "J" ]; then
    echo "OpenRouter-Schlüssel eingeben. Die Eingabe wird nicht angezeigt."
    echo "Den Schlüssel gibt es unter https://openrouter.ai/keys"
    printf "Schlüssel: "
    stty -echo 2>/dev/null
    read -r schluessel
    stty echo 2>/dev/null
    echo
    if [ -z "$schluessel" ]; then
        echo "Kein Schlüssel eingegeben, Abbruch."
        exit 1
    fi
    cat > .env <<ENVEOF
LR_BASE_URL=https://openrouter.ai/api/v1
LR_API_KEY=$schluessel
ENVEOF
    chmod 600 .env
    echo ".env angelegt, nur für dich lesbar."
fi
echo

# 4. Startskript, damit man die Umgebung nicht jedes Mal von Hand aktiviert.
cat > lr <<'LREOF'
#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
# shellcheck disable=SC1091
. .venv/bin/activate
exec python3 -m liebesroman.cli "$@"
LREOF
chmod +x lr
echo "Startskript ./lr angelegt."
echo

# 5. Verbindung prüfen
echo "Prüfe die Verbindung zu OpenRouter ..."
if ./lr modelle "mistral small" >/dev/null 2>&1; then
    echo "Verbindung steht."
else
    echo "WARNUNG: Die Modellliste konnte nicht abgerufen werden."
    echo "Prüfe den Schlüssel in .env und die Internetverbindung."
fi

echo
echo "Fertig. Ab jetzt alles über ./lr, zum Beispiel:"
echo
echo "  ./lr modelle \"drummer\"       zeigt verfügbare Modelle mit Preis"
echo "  ./lr vergleich lauf1 A B C    Testset blind über mehrere Modelle"
echo "  ./lr weiter meine -n 10       zehn Szenen einer Geschichte schreiben"
echo
