param([string]$Python = ".venv\Scripts\python.exe")

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --windowed --onefile `
        --name StrongholdAssistant --add-data "$PSScriptRoot/data;data" `
        --add-data "$PSScriptRoot/licenses;licenses" --collect-data rapidocr `
        --collect-binaries onnxruntime --hidden-import onnxruntime `
        --collect-binaries maa --collect-data maa --copy-metadata MaaFw `
        --workpath build --specpath build main.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
