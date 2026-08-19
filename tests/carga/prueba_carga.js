import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 5 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<800'],
    http_req_failed: ['rate<0.05'],
  },
};

const BASE_URL = 'http://localhost:8000';

const textos = [
  'corrige el error de conexion a la base de datos',
  'actualiza el readme con instrucciones nuevas',
  'agrega un nuevo endpoint para exportar reportes',
  'escribe pruebas con pytest para el modulo de login',
  'refactoriza el modulo de autenticacion para simplificarlo',
  'actualiza la version de las dependencias del proyecto',
  'hola mundo',
];

export default function () {
  const texto = textos[Math.floor(Math.random() * textos.length)];
  const payload = JSON.stringify({ texto, motor: 'eco' });
  const params = { headers: { 'Content-Type': 'application/json' } };

  const res = http.post(`${BASE_URL}/clasificar`, payload, params);

  check(res, {
    'status es 200': (r) => r.status === 200,
    'respuesta incluye tipo': (r) => JSON.parse(r.body).tipo !== undefined,
  });

  sleep(1);
}
