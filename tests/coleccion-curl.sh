#!/usr/bin/env bash
# ============================================================
#  COLECCION DE PRUEBAS CON CURL
# ============================================================
#
#  El enunciado pide una "coleccion de pruebas (Postman o
#  curl)" como evidencia del laboratorio de FHIR, y una
#  "coleccion de pruebas" entre los entregables de la Fase 5.
#  Esto es esa coleccion: cada peticion esta numerada, dice
#  que comprueba y se puede copiar y pegar por separado.
#
#      bash tests/coleccion-curl.sh
#      bash tests/coleccion-curl.sh 3        # solo el bloque 3
#
#  Requisitos: el sistema levantado con docker compose up.
#  Todos los datos son sinteticos.
# ============================================================

set -u

BUS=http://localhost:8002          # HSB
APP=http://localhost:8001          # API y portal
HAPI=http://localhost:8080/fhir    # servidor FHIR R4

SOLO="${1:-todos}"

azul()  { printf '\n\033[1;34m%s\033[0m\n' "$*"; }
gris()  { printf '\033[0;90m%s\033[0m\n' "$*"; }
titulo(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

# Muestra el comando y luego lo ejecuta, para que quede claro
# cual es la peticion exacta que produjo cada respuesta.
peticion() {
    local que="$1"; shift
    azul "$que"
    gris "\$ $*"
    "$@" 2>/dev/null | head -c 900
    echo
}

corre() { [ "$SOLO" = "todos" ] || [ "$SOLO" = "$1" ]; }


# ============================================================
if corre 1; then
titulo "1. SALUD Y METRICAS DE CADA SERVICIO  (RNF3)"
# El enunciado exige /health y /metrics en cada servicio.

peticion "1.1  Salud del bus" \
    curl -s "$BUS/health"

peticion "1.2  Salud de la API y el portal" \
    curl -s "$APP/health"

peticion "1.3  Metricas del bus: mensajes por minuto, latencia, fallidos" \
    curl -s "$BUS/metrics"
fi


# ============================================================
if corre 2; then
titulo "2. PRIMERAS INTERACCIONES CON FHIR  (Lab FHIR)"
# metadata, crear, leer y buscar, que es justo lo que pedia
# el laboratorio de FHIR.

peticion "2.1  metadata: que sabe hacer este servidor FHIR" \
    curl -s "$HAPI/metadata?_summary=true"

peticion "2.2  Buscar un Patient por su documento" \
    curl -s "$HAPI/Patient?identifier=urn:co:minsalud:documento|1098765432"

peticion "2.3  Buscar las Observation de ese paciente" \
    curl -s "$HAPI/Observation?subject.identifier=urn:co:minsalud:documento|1098765432"

peticion "2.4  Buscar las Condition en CIE-10" \
    curl -s "$HAPI/Condition?code=http://hl7.org/fhir/sid/icd-10|E11"
fi


# ============================================================
if corre 3; then
titulo "3. INGESTA EN LOS TRES FORMATOS  (RF1, RF2, RF3)"
# Una sede por formato. La clave de sede va en la cabecera;
# en produccion saldria de una variable de entorno.

CLAVE="DESARROLLO-CLAVE-DE-SEDE"

azul "3.1  Sede 1 (Sincelejo): HL7 v2 ADT^A01 por HTTP"
gris "     (en la demo real entra por MLLP al puerto 6661, via Mirth)"
printf 'MSH|^~\\&|HIS|HOSP|MIRTH|FHIR|20261006210000||ADT^A01|MSG9001|P|2.5\rPID|1||1098765432^^^HOSP^MR||Perez^Maria||19850722|F\rPV1|1|O|CONSULTA^^^HOSP||||2002^Gomez^Carlos^M\r' \
  | curl -s -X POST "$BUS/ingesta/hl7?sede=sede1" \
        -H "X-Sede-Clave: $CLAVE" \
        -H "Content-Type: text/plain" --data-binary @- | head -c 600
echo

azul "3.2  Sede 2 (Cartagena): CSV"
curl -s -X POST "$BUS/ingesta/csv?sede=sede2" \
     -H "X-Sede-Clave: $CLAVE" \
     -H "Content-Type: text/plain" \
     --data-binary @tests/sede2-admision.csv | head -c 600
echo

azul "3.3  Sede 3 (Corozal): JSON"
curl -s -X POST "$BUS/ingesta/json?sede=sede3" \
     -H "X-Sede-Clave: $CLAVE" \
     -H "Content-Type: application/json" \
     --data-binary @tests/sede3-admision.json | head -c 600
echo
fi


# ============================================================
if corre 4; then
titulo "4. IDEMPOTENCIA: el mismo mensaje dos veces  (RF3)"
# Criterio del enunciado: "reenviar un mensaje no crea
# duplicados". Se responde DUPLICADO y no se crea nada.

CLAVE="DESARROLLO-CLAVE-DE-SEDE"
azul "4.1  Se reenvia el CSV de la sede 2, identico"
curl -s -X POST "$BUS/ingesta/csv?sede=sede2" \
     -H "X-Sede-Clave: $CLAVE" \
     -H "Content-Type: text/plain" \
     --data-binary @tests/sede2-admision.csv | head -c 400
echo
gris "     Se espera estado DUPLICADO. La garantia es una"
gris "     restriccion UNIQUE sobre el hash del contenido."
fi


# ============================================================
if corre 5; then
titulo "5. VALIDACION: un mensaje invalido se RECHAZA  (RF3)"
# Error frecuente segun el enunciado: transformar sin validar.
# Un mensaje malo debe quedar rechazado con un motivo legible.

CLAVE="DESARROLLO-CLAVE-DE-SEDE"
azul "5.1  CSV al que le faltan columnas"
echo "9999999999,SIN APELLIDO" \
  | curl -s -X POST "$BUS/ingesta/csv?sede=sede2" \
         -H "X-Sede-Clave: $CLAVE" \
         -H "Content-Type: text/plain" --data-binary @- | head -c 400
echo

azul "5.2  HL7 sin el segmento PID (sin paciente)"
printf 'MSH|^~\\&|HIS|HOSP|MIRTH|FHIR|20261006210000||ADT^A01|MSG9999|P|2.5\r' \
  | curl -s -X POST "$BUS/ingesta/hl7?sede=sede1" \
         -H "X-Sede-Clave: $CLAVE" \
         -H "Content-Type: text/plain" --data-binary @- | head -c 400
echo
fi


# ============================================================
if corre 6; then
titulo "6. LA COLA Y LA COLA DE MENSAJES MUERTOS  (RF3)"

peticion "6.1  Estado de la cola" \
    curl -s "$BUS/cola?limite=10"

peticion "6.2  Mensajes muertos (DLQ)" \
    curl -s "$BUS/dlq"
gris "     Para reprocesar uno:  curl -X POST $BUS/reprocesar/<hash>"
fi


# ============================================================
if corre 7; then
titulo "7. AUTENTICACION Y ROLES  (RF5)"
# Usuarios sinteticos; sus claves estan en infra/bus-schema.sql.

azul "7.1  Inicio de sesion del medico"
TOKEN_MEDICO=$(curl -s -X POST "$BUS/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"usuario":"drcarlos","clave":"medico.demo"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")
gris "     token recibido: ${TOKEN_MEDICO:0:40}..."

azul "7.2  Inicio de sesion del paciente"
TOKEN_PACIENTE=$(curl -s -X POST "$APP/api/portal/login" \
    -H "Content-Type: application/json" \
    -d '{"usuario":"maria","clave":"maria.demo"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")
gris "     token recibido: ${TOKEN_PACIENTE:0:40}..."

azul "7.3  PERMITIDO: la paciente consulta SU PROPIA historia"
curl -s -o /dev/null -w "     HTTP %{http_code}\n" \
    "$APP/api/portal/hc/1098765432" \
    -H "Authorization: Bearer $TOKEN_PACIENTE"

azul "7.4  DENEGADO: la misma paciente pide la historia de OTRO"
curl -s "$APP/api/portal/hc/1033445566" \
    -H "Authorization: Bearer $TOKEN_PACIENTE" | head -c 300
echo
gris "     Se espera 403. El documento va firmado dentro del token,"
gris "     asi que no basta con cambiar el numero de la direccion."

azul "7.5  DENEGADO: sin token"
curl -s -o /dev/null -w "     HTTP %{http_code}\n" \
    "$APP/api/portal/hc/1098765432"

azul "7.6  DENEGADO: token manipulado (se le cambia la firma)"
curl -s -o /dev/null -w "     HTTP %{http_code}\n" \
    "$APP/api/portal/hc/1098765432" \
    -H "Authorization: Bearer ${TOKEN_PACIENTE}xx"
fi


# ============================================================
if corre 8; then
titulo "8. CONSULTA UNIFICADA EN LAS TRES SEDES  (RF4)"

TOKEN_MEDICO=$(curl -s -X POST "$APP/api/portal/login" \
    -H "Content-Type: application/json" \
    -d '{"usuario":"drcarlos","clave":"medico.demo"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")

peticion "8.1  Historia clinica unificada de un paciente" \
    curl -s "$APP/api/portal/hc/1098765432" \
         -H "Authorization: Bearer $TOKEN_MEDICO"
gris "     El campo 'completo' dice si respondieron los tres nodos."

peticion "8.2  Tablero de cobertura FHIR por sede" \
    curl -s "$APP/api/portal/cobertura" \
         -H "Authorization: Bearer $TOKEN_MEDICO"
fi


# ============================================================
if corre 9; then
titulo "9. BITACORA ENCADENADA POR HASH  (RF5)"

TOKEN_AUDITOR=$(curl -s -X POST "$BUS/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"usuario":"auditor1","clave":"auditor.demo"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")

peticion "9.1  Ultimos eventos de la bitacora" \
    curl -s "$BUS/auditoria?limite=5" \
         -H "Authorization: Bearer $TOKEN_AUDITOR"

peticion "9.2  Verificar la integridad de toda la cadena" \
    curl -s "$BUS/auditoria/verificar" \
         -H "Authorization: Bearer $TOKEN_AUDITOR"
gris "     Para la prueba de alteracion:  python3 tests/verificar-auditoria.py"
fi


echo
echo "============================================================"
echo " Fin de la coleccion."
echo " Pruebas relacionadas:"
echo "   python3 tests/prueba-normalizador.py   unidad, sin red"
echo "   python3 tests/prueba-roles.py          permisos por rol"
echo "   python3 tests/prueba-vistas.py         las cuatro vistas"
echo "   python3 tests/prueba-degradacion.py    caida de una sede"
echo "   python3 tests/verificar-auditoria.py   alteracion detectada"
echo "============================================================"
