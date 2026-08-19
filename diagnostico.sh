#!/usr/bin/env bash
set -uo pipefail

echo "== Clasificador de Commits IA -- diagnostico =="
echo

echo "-- Sistema --"
if command -v uname >/dev/null 2>&1; then
    uname -a
else
    echo "uname no disponible (Windows sin WSL/Git Bash con soporte limitado)."
fi
echo

echo "-- Versiones --"

if command -v git >/dev/null 2>&1; then
    echo "git: $(git --version)"
else
    echo "git: NO instalado"
fi

if command -v docker >/dev/null 2>&1; then
    echo "docker: $(docker --version)"
else
    echo "docker: NO instalado"
fi

if docker compose version >/dev/null 2>&1; then
    echo "docker compose: $(docker compose version)"
else
    echo "docker compose: NO instalado"
fi

if command -v ollama >/dev/null 2>&1; then
    echo "ollama: $(ollama --version)"
else
    echo "ollama: NO instalado"
fi

echo

echo "-- Estado de servicios (docker compose ps) --"
if command -v docker >/dev/null 2>&1; then
    docker compose ps
else
    echo "docker no disponible, no se puede consultar el estado de los servicios."
fi

echo

echo "-- Modelos de Ollama instalados --"
if command -v ollama >/dev/null 2>&1; then
    ollama list
else
    echo "Ollama no esta instalado, no hay modelos que listar."
fi
