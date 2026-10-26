@echo off
REM Start Ollama with iGPU / Vulkan acceleration (Windows).
REM Double-click or run: scripts\start_ollama_gpu.cmd

set OLLAMA_VULKAN=1
set OLLAMA_IGPU_ENABLE=1

echo OLLAMA_VULKAN=%OLLAMA_VULKAN%
echo OLLAMA_IGPU_ENABLE=%OLLAMA_IGPU_ENABLE%
echo Starting ollama serve (GPU flags set for this process)...

ollama serve
