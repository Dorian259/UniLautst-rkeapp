# Einmalige Einrichtung unter Windows.
# Aufruf in PowerShell:  powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Einrichtung der Liebesroman-Pipeline"
Write-Host ""

# 1. Python finden. Unter Windows heisst der Befehl je nach Installation
#    anders, deshalb der Reihe nach probieren.
$python = $null
foreach ($kandidat in @("py", "python", "python3")) {
    try {
        $version = & $kandidat --version 2>&1
        if ($LASTEXITCODE -eq 0) { $python = $kandidat; break }
    } catch { }
}
if (-not $python) {
    Write-Host "FEHLER: Python nicht gefunden."
    Write-Host "Installieren von https://www.python.org/downloads/"
    Write-Host "Beim Installieren den Haken bei 'Add Python to PATH' setzen."
    exit 1
}
Write-Host "Python gefunden: $(& $python --version 2>&1)"

# 2. Eigene Umgebung, damit nichts am System-Python haengt.
if (-not (Test-Path ".venv")) {
    Write-Host "Lege eine eigene Python-Umgebung an (.venv) ..."
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "FEHLER beim Anlegen der Umgebung."; exit 1 }
}
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "Installiere Abhängigkeiten ..."
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "FEHLER bei pip install."; exit 1 }
Write-Host "Abhängigkeiten installiert."
Write-Host ""

# 3. Schluessel
$neuSchreiben = $true
if ((Test-Path ".env") -and (Select-String -Path ".env" -Pattern "^LR_API_KEY=sk-" -Quiet)) {
    Write-Host "Es gibt schon eine .env mit einem Schlüssel."
    $antwort = Read-Host "Überschreiben? [j/N]"
    if ($antwort -ne "j" -and $antwort -ne "J") { $neuSchreiben = $false }
}

if ($neuSchreiben) {
    Write-Host "OpenRouter-Schlüssel eingeben. Die Eingabe wird nicht angezeigt."
    Write-Host "Den Schlüssel gibt es unter https://openrouter.ai/keys"
    $sicher = Read-Host "Schlüssel" -AsSecureString
    $schluessel = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sicher))
    if ([string]::IsNullOrWhiteSpace($schluessel)) {
        Write-Host "Kein Schlüssel eingegeben, Abbruch."
        exit 1
    }
    # Ohne Stückliste schreiben, sonst steht ein unsichtbares Zeichen vor der
    # ersten Variablen und der Name wird nicht erkannt.
    $inhalt = "LR_BASE_URL=https://openrouter.ai/api/v1`nLR_API_KEY=$schluessel`n"
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot ".env"), $inhalt,
        (New-Object System.Text.UTF8Encoding $false))
    Write-Host ".env angelegt."
}
Write-Host ""

# 4. Startskript, damit man die Umgebung nicht jedes Mal von Hand aktiviert.
$starter = "@echo off`r`n.venv\Scripts\python.exe -m liebesroman.cli %*`r`n"
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "lr.cmd"), $starter,
    (New-Object System.Text.ASCIIEncoding))
Write-Host "Startskript lr.cmd angelegt."
Write-Host ""

# 5. Verbindung pruefen
Write-Host "Prüfe die Verbindung zu OpenRouter ..."
& $venvPython -m liebesroman.cli modelle "mistral small" *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Verbindung steht."
} else {
    Write-Host "WARNUNG: Die Modellliste konnte nicht abgerufen werden."
    Write-Host "Prüfe den Schlüssel in .env und die Internetverbindung."
}

Write-Host ""
Write-Host "Fertig. Ab jetzt alles über lr, zum Beispiel:"
Write-Host ""
Write-Host "  lr modelle ""drummer""        zeigt verfügbare Modelle mit Preis"
Write-Host "  lr vergleich lauf1 A B C     Testset blind über mehrere Modelle"
Write-Host "  lr weiter meine -n 10        zehn Szenen einer Geschichte schreiben"
Write-Host ""
