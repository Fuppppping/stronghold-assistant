param([string]$Python = ".venv\Scripts\python.exe")

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --windowed --onefile `
        --name StrongholdAssistant --add-data "$PSScriptRoot/data;data" --collect-data rapidocr `
        --collect-binaries onnxruntime --hidden-import onnxruntime `
        --workpath build --specpath build main.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
