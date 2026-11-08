#!/bin/bash
# ============================================================
#  Carga y despliega el canal de Mirth por su API REST.
#
#  POR QUE AUTOMATIZADO Y NO POR LA CONSOLA:
#  El enunciado exige que "docker compose up" deje el sistema
#  funcionando "sin pasos manuales fuera del README". Importar el
#  canal a mano por la consola Java rompia ese requisito.
#
#  Es idempotente: si el canal ya existe, no hace nada.
# ============================================================
set -e

MIRTH="https://mirth:8443/api"
AUTH="admin:admin"
PLANTILLA="/canales/canal-sede1-mllp.xml"
CANAL="/tmp/canal-sede1-mllp.xml"

# ------------------------------------------------------------
#  La clave de servicio NO esta en el XML del canal, que si va
#  al repositorio. En el XML hay un marcador __CLAVE_SEDE__ y
#  aqui se cambia por el valor real que viene del entorno. El
#  resultado se escribe en /tmp porque /canales esta montado de
#  solo lectura, justo para que nadie le escriba la clave dentro.
# ------------------------------------------------------------
: "${SEDE_CLAVE:=DESARROLLO-CLAVE-DE-SEDE}"
sed "s|__CLAVE_SEDE__|$SEDE_CLAVE|" "$PLANTILLA" > "$CANAL"

api() {
  curl -sk -u "$AUTH" -H "X-Requested-With: cargador" "$@"
}

echo "esperando a que Mirth responda..."
for i in $(seq 1 60); do
  if api -o /dev/null -w "" "$MIRTH/server/version" 2>/dev/null; then
    v=$(api "$MIRTH/server/version" 2>/dev/null)
    if [ -n "$v" ]; then echo "  Mirth $v listo"; break; fi
  fi
  sleep 3
  [ $i -eq 60 ] && { echo "ERROR: Mirth no respondio en 180s" >&2; exit 1; }
done

# El id va dentro del propio XML del canal
ID=$(grep -oE '<id>[0-9a-f-]{36}</id>' "$CANAL" | head -1 | sed 's/<[^>]*>//g')
echo "  id del canal: $ID"

if api "$MIRTH/channels" 2>/dev/null | grep -q "$ID"; then
  echo "  el canal ya estaba cargado"
else
  echo "cargando el canal..."
  api -X POST -H "Content-Type: application/xml" \
      --data-binary @"$CANAL" "$MIRTH/channels" -o /dev/null -w "  HTTP %{http_code}\n"
fi

echo "desplegando..."
api -X POST -H "Content-Type: application/xml" \
    --data-binary "<set><string>$ID</string></set>" \
    "$MIRTH/channels/_deploy" -o /dev/null -w "  HTTP %{http_code}\n"

sleep 5
echo
echo "=== Canales desplegados ==="
api "$MIRTH/channels" 2>/dev/null | grep -oE '<name>[^<]*</name>' | head -5
echo "canal listo."
