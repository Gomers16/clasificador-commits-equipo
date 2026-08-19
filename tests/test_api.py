from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responde_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_clasificar_detecta_fix():
    resp = client.post(
        "/clasificar",
        json={"texto": "corrige el error de login", "motor": "eco"},
    )
    assert resp.status_code == 200
    assert resp.json()["tipo"] == "fix"


def test_clasificar_default_chore():
    resp = client.post("/clasificar", json={"texto": "hola mundo"})
    assert resp.status_code == 200
    assert resp.json()["tipo"] == "chore"


def test_clasificar_detecta_docs():
    resp = client.post(
        "/clasificar", json={"texto": "actualiza el manual de usuario"}
    )
    assert resp.status_code == 200
    assert resp.json()["tipo"] == "docs"


def test_clasificar_detecta_test():
    resp = client.post(
        "/clasificar",
        json={"texto": "escribe pruebas con pytest para el modulo de login"},
    )
    assert resp.status_code == 200
    assert resp.json()["tipo"] == "test"


def test_clasificar_detecta_feat():
    resp = client.post(
        "/clasificar",
        json={"texto": "agrega un nuevo endpoint para exportar reportes"},
    )
    assert resp.status_code == 200
    assert resp.json()["tipo"] == "feat"


def test_inferencias_devuelve_lista():
    resp = client.get("/inferencias")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
