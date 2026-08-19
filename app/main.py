import os
import re
import time
from typing import Literal

import psycopg2
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Clasificador de Commits IA")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "clasificador_commits")
DB_USER = os.getenv("DB_USER", "app_ia")
DB_PASSWORD = os.getenv("DB_PASSWORD", "app_ia_password")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

MOTOR_ECO_MODELO = "eco-reglas-v1"

# Orden de evaluacion = orden de prioridad cuando el texto coincide con varias reglas.
REGLAS_CLASIFICACION: list[tuple[str, re.Pattern]] = [
    ("fix", re.compile(r"fix|corrig|arregl|error|bug|falla", re.IGNORECASE)),
    ("docs", re.compile(r"doc|readme|manual|coment", re.IGNORECASE)),
    ("test", re.compile(r"test|prueba|pytest|cobertura", re.IGNORECASE)),
    ("chore", re.compile(r"actualiz|dependenc|version|limpi|config", re.IGNORECASE)),
    ("refactor", re.compile(r"refactor|reorganiz|renombr|simplific", re.IGNORECASE)),
    ("feat", re.compile(r"agreg|add|nuev|implement|crear|feature", re.IGNORECASE)),
]


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


class ClasificarRequest(BaseModel):
    texto: str
    motor: Literal["eco", "ollama"] = "eco"


class ClasificarResponse(BaseModel):
    motor: str
    modelo: str
    entrada: str
    tipo: str
    latencia_ms: float


def clasificar_por_reglas(texto: str) -> str:
    for tipo, patron in REGLAS_CLASIFICACION:
        if patron.search(texto):
            return tipo
    return "chore"


def ejecutar_motor_eco(texto: str) -> tuple[str, str]:
    return MOTOR_ECO_MODELO, clasificar_por_reglas(texto)


def ejecutar_motor_ollama(texto: str) -> tuple[str, str]:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": texto, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502, detail=f"Error consultando Ollama: {exc}"
        ) from exc
    return OLLAMA_MODEL, resp.json().get("response", "")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/clasificar", response_model=ClasificarResponse)
def clasificar(payload: ClasificarRequest):
    inicio = time.perf_counter()

    if payload.motor == "eco":
        modelo, tipo = ejecutar_motor_eco(payload.texto)
    else:
        modelo, tipo = ejecutar_motor_ollama(payload.texto)

    latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inferencias (motor, modelo, entrada, salida, latencia_ms, fecha)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (payload.motor, modelo, payload.texto, tipo, latencia_ms),
            )
    finally:
        conn.close()

    return ClasificarResponse(
        motor=payload.motor,
        modelo=modelo,
        entrada=payload.texto,
        tipo=tipo,
        latencia_ms=latencia_ms,
    )


@app.get("/inferencias")
def listar_inferencias(limite: int = 20):
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, motor, modelo, entrada, salida, latencia_ms, fecha
                FROM inferencias
                ORDER BY id DESC
                LIMIT %s
                """,
                (limite,),
            )
            filas = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": fila[0],
            "motor": fila[1],
            "modelo": fila[2],
            "entrada": fila[3],
            "salida": fila[4],
            "latencia_ms": fila[5],
            "fecha": fila[6],
        }
        for fila in filas
    ]
