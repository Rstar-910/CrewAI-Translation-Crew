#!/bin/bash
set -e

# Install uv if not already present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make uv available in the current shell session
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create virtual environment and install dependencies
echo "Setting up Python environment with uv..."
uv sync

# Install Ollama
echo "Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
echo "Pulling models (this may take several minutes)..."
ollama pull mistral
ollama pull mistral:7b
ollama pull mistral-nemo
ollama pull llama3.2:3b

# Start Ollama in the background
nohup ollama serve > ollama.log 2>&1 &
sleep 5

# Verify the service is up
curl -s http://localhost:11434/api/tags && echo "" || echo "Warning: Ollama not yet reachable — check ollama.log"

echo ""
echo "Setup complete. Run the translation system with:"
echo "  uv run python main.py"
