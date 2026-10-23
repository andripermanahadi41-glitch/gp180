@echo off
cd /d "%~dp0"
where python >nul 2>&1 || (
  echo Python introuvable. https://www.python.org/downloads/
  echo IMPORTANT : cocher "Add python.exe to PATH" a l'installation.
  pause & exit /b 1
)
if not exist "data\gp180_models_all.json" (
  echo Dossier data\ manquant ou incomplet.
  echo Extrais tout GP180_Studio.zip dans : %CD%
  pause & exit /b 1
)
if not exist "template.prst" (
  echo template.prst manquant. Extrais tout GP180_Studio.zip dans : %CD%
  pause & exit /b 1
)
start "" pythonw gp180_studio.py
