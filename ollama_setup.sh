#!/bin/bash

# Install ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the mistral model (this might take a few minutes)
ollama pull mistral
ollama pull mistral:7b
ollama pull mistral-nemo
ollama pull llama3.2:3b

# Start ollama service in the background
nohup ollama serve > ollama.log 2>&1 &

# Wait a moment for the service to start
sleep 5

# Test if it's working
curl http://localhost:11434/api/tags

echo "\nOllama is ready! You can now run your translation script."