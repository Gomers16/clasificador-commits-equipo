#!/usr/bin/env bash
set -euo pipefail

echo "== Clasificador de Commits IA -- setup =="
echo

# 1. Docker
if command -v docker >/dev/null 2>&1; then
    echo "[OK] Docker detectado: $(docker --version)"
else
    echo "[FALTA] Docker no esta disponible en el PATH."
    echo "        Instala Docker Desktop (Windows/Mac) o Docker Engine (Linux):"
    echo "        https://www.docker.com/products/docker-desktop/"
    echo "        En Windows, asegurate de que el backend WSL2 este habilitado."
    exit 1
fi

# 2. Ollama (opcional)
if command -v ollama >/dev/null 2>&1; then
    echo "[OK] Ollama detectado: $(ollama --version)"
else
    echo "[OPCIONAL] Ollama no esta disponible en el PATH."
    echo "           Solo es necesario si vas a usar motor=\"ollama\"."
    echo "           Instalacion:"
    echo "             Windows: winget install -e --id Ollama.Ollama"
    echo "             Mac/Linux: https://ollama.com/download"
    echo "           Luego descarga un modelo, ej.: ollama pull qwen2.5-coder:1.5b"
fi

echo

# 3. .env
if [ -f .env ]; then
    echo "[OK] .env ya existe, no se sobreescribe."
else
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "[OK] .env creado a partir de .env.example."
        echo "     Revisa POSTGRES_PASSWORD y OLLAMA_MODEL si quieres cambiarlos"
        echo "     (deja DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME, DB_USER como estan)."
    else
        echo "[ERROR] No se encontro .env.example. Abortando."
        exit 1
    fi
fi

echo

# 4. Levantar el stack
echo "Levantando el stack con docker compose up -d --build ..."
if docker compose up -d --build; then
    echo
    echo "[EXITO] El stack quedo arriba."
    echo "        Verifica con: docker compose ps"
    echo "        Prueba con:   curl http://localhost:8000/health"
else
    echo
    echo "[ERROR] docker compose up fallo. Revisa el mensaje de error arriba."
    echo "        Causas comunes: Docker Desktop no esta corriendo, o el puerto"
    echo "        8000/5432 ya esta en uso por otro proceso."
    exit 1
fi
