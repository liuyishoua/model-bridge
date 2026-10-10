$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConverterExe = Join-Path $ProjectRoot '.runtime\converter-venv\Scripts\python.exe'
$ConverterScript = Join-Path $ProjectRoot '.runtime\llama.cpp\convert_hf_to_gguf.py'
$SourceModel = Join-Path (Split-Path -Parent $ProjectRoot) 'models\gpt-oss-20b'
$OutputModel = Join-Path $ProjectRoot 'data\converted\gpt-oss-20b-mxfp4.gguf'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputModel) | Out-Null
& $ConverterExe -u $ConverterScript $SourceModel --outfile $OutputModel --outtype auto
if ($LASTEXITCODE -ne 0) { throw 'Official llama.cpp conversion failed; inspect output before importing.' }
$env:OLLAMA_HOST = '127.0.0.1:11434'
Push-Location $ProjectRoot
try {
    & (Join-Path $ProjectRoot '.runtime\ollama\ollama.exe') create leo-gpt-oss:20b -f (Join-Path $ProjectRoot 'Modelfile')
    if ($LASTEXITCODE -ne 0) { throw 'Ollama model import failed.' }
} finally { Pop-Location }
