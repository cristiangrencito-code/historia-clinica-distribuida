# Plataforma de Interoperabilidad en Salud

Parcial Final de Sistemas Distribuidos.

**Equipo:** Cristian Gómez · Gerneidis Berrios
Red hospitalaria con tres sedes — **Sincelejo, Cartagena y Corozal** — que
envían información clínica en formatos distintos y necesitan una historia
clínica única.

> Todos los datos de este repositorio son **sintéticos**. Ningún dato real de
> pacientes entra al repositorio ni a la demostración.

---

## Levantar todo

```bash
docker compose up -d
```

Un solo comando. No hay pasos manuales: las tres bases se crean y se llenan
solas, el canal de Mirth se carga y se despliega por su API REST, y el bus
arranca con su cola y su bitácora.

Para comprobar que está listo:

```bash
curl -s http://localhost:8001/health | python3 -m json.tool
```

| Servicio | Dirección | Qué es |
|---|---|---|
| Portal clínico | http://localhost:8001/login | Las cuatro vistas por rol |
| Panel de nodos | http://localhost:8001/home | Consola de la base distribuida |
| HSB (bus) | http://localhost:8002/health | Bus de integración |
| HAPI FHIR | http://localhost:8080/fhir | Servidor FHIR R4 |
| Mirth Connect | https://localhost:8443 | Consola de administración |
| MLLP sede 1 | `localhost:6661` | Entrada HL7 v2 |
| Nodos | 5433 / 5434 / 5435 | PostgreSQL 1, 2 y 3 |

Parar y borrarlo todo: `docker compose down -v`

---

## Arquitectura

```
 Sede 1  HL7 v2 ──MLLP:6661──> MIRTH ──HTTP──┐
         (ACK inmediato)                      │
                                              ▼
 Sede 2  CSV   ──/ingesta/csv ───────────>  HSB  ──> HAPI FHIR R4
 Sede 3  JSON  ──/ingesta/json ──────────┘   │
                                             └──> nodo1 / nodo2 / nodo3
                                                  (fragmentados por documento)
```

**Mirth** es el adaptador de protocolo: habla MLLP, responde el ACK y reenvía
el mensaje crudo. **El HSB** hace el trabajo de bus — valida, transforma,
mapea terminologías, garantiza la entrega y audita. El reparto no es
arbitrario: la propia plantilla del curso señala que Mirth tiene
*monitorización limitada sin complementos*, y la cola, las métricas y la cola
de mensajes muertos son justamente lo que no se quiere delegar.

### Las tres garantías del bus

1. **Idempotencia** — cada mensaje se identifica por el SHA-256 de su
   contenido, con una restricción `UNIQUE` en la base. La garantía vive donde
   está el estado compartido, no en el código: entre un `SELECT` y un `INSERT`
   podría colarse otro hilo con el mismo mensaje.
2. **Reintentos con retroceso exponencial** — si HAPI está caído el mensaje
   no se pierde: queda `FALLIDO` con fecha de próximo intento y un hilo en
   segundo plano lo reintenta esperando cada vez más.
3. **Cola de mensajes muertos** — agotados los intentos pasa a `MUERTO`, con
   el motivo guardado y el contenido original para poder reprocesarlo.

`RECHAZADO` y `MUERTO` no son lo mismo: el primero es un mensaje mal formado
(reintentarlo daría el mismo error), el segundo es un mensaje correcto cuyo
destino falló.

---

## Las cuatro vistas

Entrar en http://localhost:8001/login con los usuarios sintéticos que define
[`infra/bus-schema.sql`](infra/bus-schema.sql) (usuario y clave están
documentados ahí junto a la tabla `usuario_sistema`).

| Rol | Vista | Qué ve |
|---|---|---|
| `paciente` | Mi Historia | Solo **su** historia; el documento viene firmado en el token |
| `admisionista` | Admisión | Busca y admite. **Sin diagnósticos ni medicamentos** |
| `medico` | Historia Clínica | La historia completa de las tres sedes |
| `auditor` | Reporte de HC | Tablero de cobertura, métricas y bitácora |

El control no está en la pantalla. El menú oculta lo que el rol no puede, pero
quien llame al endpoint a mano con `curl` recibe el mismo **403**, y el
intento queda anotado en la bitácora.

El admisionista no ve diagnósticos porque **el servidor no se los envía**: la
respuesta se construye de cero con los campos permitidos, no borrando los
prohibidos. Así, si mañana se añade una columna clínica a la consulta, no se
filtra sola.

---

## Demostraciones

### RF2 — Pruebas unitarias del normalizador

```bash
python3 tests/prueba-normalizador.py
```

43 comprobaciones, doce de ellas sobre entradas inválidas. No hace falta
levantar nada: importa `hsb/normalizador.py` y `hsb/parsers.py` directamente,
así que corre en menos de un segundo y sirve después de cada cambio.

### Todos los requisitos — Colección de peticiones

```bash
bash tests/coleccion-curl.sh        # la colección entera
bash tests/coleccion-curl.sh 7      # solo el bloque 7 (roles)
```

Nueve bloques numerados, uno por grupo de requisitos. Cada petición muestra el
comando antes de ejecutarlo, para poder copiarla por separado.

### RF1 — Tres sedes, tres formatos

```bash
bash tests/enviar-las-tres-sedes.sh
```

HL7 v2 por MLLP a través de Mirth, CSV y JSON por HTTP. Los tres acaban en el
mismo modelo canónico y salen como el mismo Bundle FHIR R4.

### RF3 — Idempotencia

Enviar dos veces el mismo mensaje: el segundo responde `DUPLICADO` y no crea
nada nuevo.

### RF5 — Roles, accesos permitidos y denegados

```bash
python3 tests/prueba-roles.py     # contra el bus
python3 tests/prueba-vistas.py    # contra el portal
```

### RF5 — La bitácora no se puede alterar

```bash
python3 tests/verificar-auditoria.py
```

Cada evento guarda el hash del anterior:
`hash_actual = SHA-256(contenido + hash_anterior)`.

Para probarlo, alterar una fila por detrás y volver a verificar:

```bash
docker exec pg_nodo1 psql -U admin -d bus_db -c "UPDATE evento_auditoria SET resultado='PERMITIDO' WHERE secuencia=(SELECT min(secuencia) FROM evento_auditoria WHERE resultado='DENEGADO')"
```

El verificador señala la fila exacta. Hace dos comprobaciones distintas:
recalcula el hash de cada fila (caza **modificaciones**) y comprueba que el
`hash_anterior` encaje con la fila previa (caza **borrados** y
reordenamientos).

### RNF — Degradación parcial

```bash
python3 tests/prueba-degradacion.py
```

Apaga una sede, luego dos, y las vuelve a levantar. La historia y el reporte
siguen respondiendo: devuelven lo que hay y avisan de que el resultado es
parcial. La recuperación es automática, sin reiniciar nada.

---

## Observabilidad

| Endpoint | Qué da |
|---|---|
| `GET :8001/health` | Estado de la app, de los tres nodos y del bus |
| `GET :8001/metrics` | Nodos vivos y cobertura FHIR |
| `GET :8002/health` | Estado del bus, de HAPI y de los nodos |
| `GET :8002/metrics` | Mensajes, latencia media, porcentaje de fallidos |
| `GET :8002/cola` | La cola del bus |
| `GET :8002/dlq` | Mensajes muertos |

`/health` distingue tres estados y no dos: `ok`, `degradado` y `caido`. Un
sistema distribuido no está vivo o muerto, tiene grados — con dos de tres
nodos en pie la app sigue sirviendo historias, solo que incompletas.

---

## Fragmentación

Reparto horizontal por rango de documento:

| Nodo | Rango | Puerto |
|---|---|---|
| nodo1 | `documento_id < 4.000.000.000` | 5433 |
| nodo2 | `4.000.000.000 ≤ documento_id < 7.000.000.000` | 5434 |
| nodo3 | `documento_id ≥ 7.000.000.000` | 5435 |

**El nodo no es la sede.** El nodo lo decide el documento; la sede la dice
`atencion.entidad_salud`. María Pérez (documento `1098765432`) vive en el
nodo1 pero tiene atenciones en las tres sedes: esa es la consulta unificada.

---

## Cobertura de normalización

El tablero mide el porcentaje de pacientes con `usuario.fhir_patient_id`
lleno. Esa columna la rellena el bus con el id **real** que devuelve HAPI al
crear el Patient, así que cada punto del tablero se puede comprobar uno por
uno contra el servidor FHIR. No es un contador aparte que pueda
desincronizarse: es la consecuencia de que la normalización ocurrió.

---

## Seguridad

- **JWT firmado** con HMAC-SHA256, implementado con la biblioteca estándar en
  [`seguridad.py`](seguridad.py). El bus emite; la app valida con el secreto
  compartido, sin una llamada de red por petición.
- **Claves** con PBKDF2-HMAC-SHA256, 120.000 iteraciones y sal por usuario.
- **Bitácora encadenada por hash**, con un único escritor (el bus) para que
  dos procesos no puedan bifurcar la cadena.
- **La ingesta exige credencial**: cabecera `X-Sede-Clave` (sistemas de sede y
  Mirth) o un token con el permiso `INGESTAR`.

Los secretos salen de `.env`, que está en `.gitignore`. Ver
[`.env.ejemplo`](.env.ejemplo). Si no existe `.env` el sistema arranca con
valores de desarrollo y `/health` lo avisa en voz alta.

```bash
cp .env.ejemplo .env     # y poner valores propios
```

---

## Estructura

```
app.py                  Aplicación web (vistas del profesor + portal)
portal.py               Las 4 vistas por rol y el tablero de cobertura
seguridad.py            JWT, PBKDF2 y la tabla de permisos
middleware.py           Consulta a los 3 nodos con tolerancia a fallos
hsb/
  bus.py                El bus: ingesta, cola, reintentos, auditoría
  parsers.py            HL7 v2 / CSV / JSON  ->  modelo canónico
  normalizador.py       Modelo canónico  ->  FHIR R4
  canal-sede1-mllp.xml  Canal de Mirth
infra/
  bus-schema.sql        mensaje_bus, evento_auditoria, ref_terminologia
  semilla-nodo*.sql     Datos sintéticos
  cargar-canal-mirth.sh Despliegue automático del canal
tests/                  Pruebas y mensajes de ejemplo
docs/presentacion/      Guion de sustentación y presentación de apoyo
docs/evidencias/        Salidas de las pruebas
```
