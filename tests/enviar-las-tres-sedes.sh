#!/bin/bash
# ============================================================
#  DEMOSTRACION DEL RF1: tres sedes, tres formatos
#
#    Sede 1  SINCELEJO   HL7 v2  por MLLP, a traves de Mirth
#    Sede 2  CARTAGENA   CSV     por HTTP, directo al bus
#    Sede 3  COROZAL     JSON    por HTTP, directo al bus
#
#  Los tres acaban en el mismo modelo canonico y salen
#  convertidos al mismo Bundle FHIR R4.
#
#  USO:   bash tests/enviar-las-tres-sedes.sh
# ============================================================

HSB="http://localhost:8002"
CLAVE="${SEDE_CLAVE:-DESARROLLO-CLAVE-DE-SEDE}"
AQUI="$(dirname "$0")"

echo
echo "============================================================"
echo " RF1 - INGESTA DESDE LAS TRES SEDES"
echo "============================================================"

echo
echo "--- SEDE 1 (SINCELEJO) - HL7 v2 por MLLP:6661 -> Mirth ---"
echo
python3 "$AQUI/enviar-hl7.py" "$AQUI/adt-mllp.hl7" localhost 6661 | tail -5

echo
echo "--- SEDE 2 (CARTAGENA) - CSV por HTTP ---"
echo
cat "$AQUI/sede2-admision.csv"
echo
curl -s -X POST "$HSB/ingesta/csv?sede=sede2" \
     -H "X-Sede-Clave: $CLAVE" \
     -H "Content-Type: text/plain" \
     --data-binary @"$AQUI/sede2-admision.csv"
echo

echo
echo "--- SEDE 3 (COROZAL) - JSON por HTTP ---"
echo
curl -s -X POST "$HSB/ingesta/json?sede=sede3" \
     -H "X-Sede-Clave: $CLAVE" \
     -H "Content-Type: application/json" \
     --data-binary @"$AQUI/sede3-admision.json"
echo

echo
echo "============================================================"
echo " ESTADO DE LA COLA DEL BUS"
echo "============================================================"
curl -s "$HSB/cola" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('  %-14s %-16s %-6s %-12s %s' % ('HASH','SEDE','FORMATO','ESTADO','DOCUMENTO'))
for m in d['mensajes'][:10]:
    print('  %-14s %-16s %-6s %-12s %s' % (
        m['hash_mensaje'], m['sede'] or '-', m['formato'],
        m['estado'], m['documento_id'] or '-'))
"

echo
echo "============================================================"
echo " RECURSOS CREADOS EN HAPI FHIR"
echo "============================================================"
for r in Patient Encounter Condition Observation; do
  n=$(curl -s "http://localhost:8080/fhir/$r?_summary=count" \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('total','?'))" 2>/dev/null)
  printf "  %-12s %s\n" "$r" "$n"
done
echo
