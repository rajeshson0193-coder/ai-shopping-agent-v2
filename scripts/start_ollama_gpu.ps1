# Start Ollama with iGPU / Vulkan acceleration (Windows).
# Run this in a separate terminal BEFORE ShopBuddy explanations.
#
# Usage:
#   .\scripts\start_ollama_gpu.ps1
#
# If ollama is already running on CPU, stop it first:
#   Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
#   Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force

$ErrorActionPreference = "Stop"

$env:OLLAMA_VULKAN = "1"
$env:OLLAMA_IGPU_ENABLE = "1"

Write-Host "OLLAMA_VULKAN=$env:OLLAMA_VULKAN"
Write-Host "OLLAMA_IGPU_ENABLE=$env:OLLAMA_IGPU_ENABLE"
Write-Host "Starting ollama serve (GPU flags set for this process)..."

ollama serve
