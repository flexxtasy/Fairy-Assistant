# One-shot installer for Windows (run in PowerShell).
# Creates a private venv and installs Fairy's only dependency (PySide6).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install "PySide6>=6.6"

Write-Host @"

Fairy installed. Examples:
  # canned-reply mode to see the UI immediately:
  .\.venv\Scripts\python.exe fairy.py --brain stub --icon-only
  # point her at a local model server (see docs\engines-and-models.md):
  .\.venv\Scripts\python.exe fairy.py --brain strata --strata-url http://127.0.0.1:11434 --icon-only

Autostart: create a shortcut in shell:startup that runs
  .\.venv\Scripts\pythonw.exe fairy.py --icon-only ...

"@
