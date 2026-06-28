# Install uv if not already present
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # Refresh PATH so uv is available immediately
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
}

# Create virtual environment and install dependencies
Write-Host "Setting up Python environment with uv..."
uv sync

# Install Ollama
Write-Host "Downloading Ollama installer..."
$installerPath = "$env:TEMP\OllamaSetup.exe"
Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installerPath
Start-Process -FilePath $installerPath -Wait
Remove-Item $installerPath

# Pull required models
Write-Host "Pulling models (this may take several minutes)..."
ollama pull mistral
ollama pull mistral:7b
ollama pull mistral-nemo
ollama pull llama3.2:3b

# Start Ollama service
Write-Host "Starting Ollama service..."
Start-Process -FilePath "ollama" -ArgumentList "serve" -RedirectStandardOutput "ollama.log" -NoNewWindow
Start-Sleep -Seconds 5

# Verify the service is running
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method GET
    Write-Host "Ollama is ready! Available models:"
    $response.models | ForEach-Object { Write-Host "  - $($_.name)" }
} catch {
    Write-Host "Warning: Could not reach Ollama at http://localhost:11434 — check ollama.log"
}

Write-Host "`nSetup complete. Run the translation system with:"
Write-Host "  uv run python main.py"
