-- Rol de aplicacion con permisos limitados sobre la tabla inferencias.
-- La contrasena aqui debe coincidir con DB_PASSWORD en .env.
CREATE ROLE app_ia WITH LOGIN PASSWORD 'app_ia_password';

CREATE TABLE IF NOT EXISTS inferencias (
    id SERIAL PRIMARY KEY,
    motor VARCHAR(20) NOT NULL CHECK (motor IN ('eco', 'ollama')),
    modelo VARCHAR(100) NOT NULL,
    entrada TEXT NOT NULL,
    salida TEXT,
    latencia_ms DOUBLE PRECISION NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT NOW()
);

GRANT CONNECT ON DATABASE clasificador_commits TO app_ia;
GRANT USAGE ON SCHEMA public TO app_ia;
GRANT SELECT, INSERT ON TABLE inferencias TO app_ia;
GRANT USAGE, SELECT ON SEQUENCE inferencias_id_seq TO app_ia;
