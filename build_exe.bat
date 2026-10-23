@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  GP-180 Studio - compilation Windows
REM  A lancer depuis un terminal NON-administrateur.
REM ============================================================
cd /d "%~dp0"
echo.
echo   Dossier de travail : %CD%
echo.

net session >nul 2>&1
if %errorlevel%==0 (
  echo   [!] Tu es en ADMINISTRATEUR. PyInstaller le deconseille et le bloquera
  echo       en version 7.0. Ferme et relance en session normale.
  echo.
  choice /c ON /n /m "  Continuer quand meme ? [O/N] "
  if errorlevel 2 exit /b 1
  echo.
)

echo [1/6] Verification des fichiers...
set MISSING=0
for %%F in (gp180_studio.py gp180_agent.py gp180lib.py gp180_i18n.py gp180_secrets.py gp180_setlist.py gp180_theme.py gp180_ui.py gp180_oauth.py gp180_lufs.py gp180_calibration.py gp180_batch.py gp180_batch_live.py gp180_midi.py gp180_usb.py template.prst icon.ico) do (
  if exist "%%F" ( echo        OK   %%F ) else ( echo        !!   %%F  MANQUANT & set MISSING=1 )
)
if exist "data\" (
  set /a NJSON=0
  for %%F in (data\*.json) do set /a NJSON+=1
  echo        OK   data\  ^(!NJSON! fichiers .json^)
  if !NJSON! LSS 15 ( echo        !!   data\ incomplet : !NJSON! trouves, 15 attendus & set MISSING=1 )
) else ( echo        !!   data\  MANQUANT & set MISSING=1 )
for %%F in (gp180_models_all.json gp180_cabs.json gp180_factory_presets.json) do (
  if not exist "data\%%F" ( echo        !!   data\%%F  MANQUANT & set MISSING=1 )
)
if !MISSING!==1 (
  echo.
  echo   ============================================================
  echo    FICHIERS MANQUANTS.
  echo.
  echo    Extrais TOUT le contenu de GP180_Studio.zip dans :
  echo      %CD%
  echo.
  echo    Le .bat, les .py, template.prst et le dossier data\
  echo    doivent etre AU MEME NIVEAU. Pas de sous-dossier GP180_Studio\.
  echo   ============================================================
  echo.
  pause & exit /b 1
)

echo.
echo [2/6] Python...
where python >nul 2>&1 || (
  echo        !! Python introuvable dans le PATH.
  echo           https://www.python.org/downloads/  ^(cocher "Add python.exe to PATH"^)
  pause & exit /b 1
)
for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo        %%V
python -c "import tkinter" 2>nul || (
  echo        !! Tkinter absent. Reinstalle Python en cochant "tcl/tk and IDLE".
  pause & exit /b 1
)
echo        Tkinter OK

echo.
echo [3/6] Environnement virtuel...
set VENV_STALE=0
if exist ".venv\Scripts\activate.bat" (
  REM Verifier que le venv pointe bien vers ce dossier (pas un venv copie d ailleurs)
  set VENV_HOME=
  for /f "tokens=2 delims==" %%A in ('findstr /i "^home" ".venv\pyvenv.cfg" 2^>nul') do set VENV_HOME=%%A
  echo !VENV_HOME! | findstr /i "%CD%" >nul 2>&1
  if errorlevel 1 (
    echo        venv perime detecte -- recreation en cours...
    rmdir /s /q ".venv"
    set VENV_STALE=1
  ) else (
    echo        reutilise ^(!VENV_HOME!^)
  )
) else (
  set VENV_STALE=1
)
if !VENV_STALE!==1 (
  python -m venv .venv || (echo        !! Echec creation venv & pause & exit /b 1)
  echo        cree
)
call ".venv\Scripts\activate.bat"

echo.
echo [4/6] PyInstaller...
python -m pip install --quiet --upgrade pip pyinstaller sounddevice pyloudnorm || (
  echo        !! Echec pip. Proxy d'entreprise ? Definis HTTPS_PROXY.
  pause & exit /b 1
)
REM mido : pure Python, installe sans compilation. Le backend rtmidi est optionnel
REM (si absent a l'execution, gp180_usb tombe en mode MIDI-only automatiquement)
python -m pip install --quiet mido || echo        Note: mido non installe ^(mode USB desactive^)
for /f "tokens=*" %%V in ('python -m PyInstaller --version 2^>^&1') do echo        version %%V

echo.
echo [5/6] Compilation ^(quelques minutes^)...
if exist "GP180_Studio.spec" del /q "GP180_Studio.spec"
if exist "build\" rmdir /s /q "build"
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name GP180_Studio ^
  --icon="icon.ico" ^
  --paths "." ^
  --hidden-import gp180lib ^
  --hidden-import gp180_agent ^
  --hidden-import gp180_i18n ^
  --hidden-import gp180_secrets ^
  --hidden-import gp180_setlist ^
  --hidden-import gp180_theme ^
  --hidden-import gp180_ui ^
  --hidden-import gp180_oauth ^
  --hidden-import gp180_lufs ^
  --hidden-import gp180_calibration ^
  --hidden-import gp180_batch ^
  --hidden-import gp180_batch_live ^
  --hidden-import gp180_midi ^
  --hidden-import gp180_usb ^
  --hidden-import sounddevice ^
  --hidden-import pyloudnorm ^
  --hidden-import mido ^
  --add-data "data;data" ^
  --add-data "template.prst;." ^
  --add-data "icon.ico;." ^
  gp180_studio.py
if not exist "dist\GP180_Studio.exe" (
  echo.
  echo        !! Compilation echouee. Lis les lignes ERROR ci-dessus.
  pause & exit /b 1
)

echo [6/6] Verification de l'auto-test...
if exist "dist\selftest.log" del /q "dist\selftest.log"
python gp180_studio.py --selftest
if errorlevel 1 (
    echo L'auto-test a echoue.
    exit /b 1
)
echo Verification OK.
if exist "dist\selftest.log" ( type "dist\selftest.log" & del /q "dist\selftest.log" )
echo        exe verifie : tables, template et encodage OK

if not exist "dist\config.json" copy "config.example.json" "dist\config.json" >nul
echo.
echo   ============================================================
echo    OK  --^>  dist\GP180_Studio.exe
echo.
echo    DERNIERE ETAPE : ouvre dist\config.json et colle ta cle API.
echo    L'exe et config.json doivent rester dans le meme dossier.
echo   ============================================================
echo.
pause