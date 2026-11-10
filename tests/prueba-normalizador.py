#!/usr/bin/env python3
"""
============================================================
 PRUEBAS UNITARIAS DEL NORMALIZADOR  (RF2 - Fase 2)
============================================================

La Fase 2 pide "normalizador con pruebas unitarias (minimo 5
casos, incluido uno invalido)". Aqui hay 43, y doce de ellos
son casos invalidos.

    python3 tests/prueba-normalizador.py

No hace falta que el sistema este levantado: estas pruebas
importan hsb/normalizador.py y hsb/parsers.py directamente y
no tocan la red ni la base de datos. Por eso corren en menos
de un segundo y se pueden lanzar despues de cada cambio.

Solo usa la biblioteca estandar.
"""

import os
import sys
import json

# El normalizador vive en hsb/, asi que hay que anadir esa
# carpeta al camino de busqueda antes de importarlo.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "hsb"))

import normalizador
import parsers


# ============================================================
#  Un comprobador minimo, para no depender de nada externo
# ============================================================

_pasadas = 0
_fallos = []


def comprobar(titulo, obtenido, esperado):
    """Compara y deja constancia. No corta la ejecucion si falla:
    interesa ver TODOS los fallos de una pasada, no solo el
    primero."""
    global _pasadas
    if obtenido == esperado:
        _pasadas += 1
        print("  ok    %s" % titulo)
    else:
        _fallos.append(titulo)
        print("  FALLA %s" % titulo)
        print("          esperaba: %r" % (esperado,))
        print("          obtuvo:   %r" % (obtenido,))


def seccion(titulo):
    print("\n--- %s ---\n" % titulo)


print("=" * 66)
print(" PRUEBAS UNITARIAS DEL NORMALIZADOR")
print("=" * 66)


# ============================================================
#  1. FECHAS DE NACIMIENTO
# ============================================================
seccion("1. normalizar_fecha: los tres formatos de las tres sedes")

comprobar("sede 1, estilo HL7 '19850722'",
          normalizador.normalizar_fecha("19850722"), "1985-07-22")
comprobar("sede 2, local '22/07/1985'",
          normalizador.normalizar_fecha("22/07/1985"), "1985-07-22")
comprobar("sede 3, ya en ISO '1985-07-22'",
          normalizador.normalizar_fecha("1985-07-22"), "1985-07-22")

seccion("2. normalizar_fecha: casos INVALIDOS (no se inventa una fecha)")

# El 31 de febrero no existe. Si el normalizador se limitara a
# cortar la cadena, lo daria por bueno.
comprobar("INVALIDO: 31 de febrero",
          normalizador.normalizar_fecha("31/02/2026"), None)
comprobar("INVALIDO: 30 de febrero en ano bisiesto",
          normalizador.normalizar_fecha("30/02/2024"), None)
comprobar("VALIDO: 29 de febrero de 2024 (bisiesto) si existe",
          normalizador.normalizar_fecha("29/02/2024"), "2024-02-29")
comprobar("INVALIDO: 29 de febrero de 2023 (no bisiesto)",
          normalizador.normalizar_fecha("29/02/2023"), None)
comprobar("INVALIDO: 31 de abril",
          normalizador.normalizar_fecha("31/04/2026"), None)
comprobar("INVALIDO: mes 13",
          normalizador.normalizar_fecha("20261301"), None)
comprobar("INVALIDO: texto que no es fecha",
          normalizador.normalizar_fecha("ayer"), None)
comprobar("INVALIDO: cadena vacia",
          normalizador.normalizar_fecha(""), None)
comprobar("INVALIDO: ausente",
          normalizador.normalizar_fecha(None), None)


# ============================================================
#  3. FECHA Y HORA DE LA ATENCION
# ============================================================
seccion("3. normalizar_fecha_hora")

comprobar("HL7 '20261012091500'",
          normalizador.normalizar_fecha_hora("20261012091500"),
          "2026-10-12T09:15:00")

# Este caso concreto es una PRUEBA DE REGRESION. Las sedes 2 y 3
# mandan la fecha sin segundos. El normalizador no reconocia ese
# formato y devolvia None, asi que el Encounter se perdia en
# silencio para dos de las tres sedes. Si alguien vuelve a tocar
# normalizar_fecha_hora, esta prueba lo avisa.
comprobar("REGRESION: ISO sin segundos '2026-10-12 09:15'",
          normalizador.normalizar_fecha_hora("2026-10-12 09:15"),
          "2026-10-12T09:15:00")
comprobar("ISO con T y sin segundos '2026-10-12T09:15'",
          normalizador.normalizar_fecha_hora("2026-10-12T09:15"),
          "2026-10-12T09:15:00")
comprobar("INVALIDO: fecha y hora ilegibles",
          normalizador.normalizar_fecha_hora("el martes"), None)


# ============================================================
#  4. GENERO
# ============================================================
seccion("4. normalizar_genero")

comprobar("'M' -> male", normalizador.normalizar_genero("M"), "male")
comprobar("'FEMENINO' -> female",
          normalizador.normalizar_genero("FEMENINO"), "female")
# FHIR exige un valor del conjunto; 'unknown' es parte de el.
# Devolver 'unknown' es mejor que dejar el campo fuera.
comprobar("desconocido -> unknown",
          normalizador.normalizar_genero("X"), "unknown")


# ============================================================
#  5. SEPARACION DEL NOMBRE  (heuristica de la sede 2)
# ============================================================
seccion("5. separar_nombre")

comprobar("'LAURA MEJIA ORTIZ'",
          normalizador.separar_nombre("LAURA MEJIA ORTIZ"),
          ("LAURA", "MEJIA ORTIZ"))
# Caso conocido en el que la heuristica FALLA: se deja escrito en
# la prueba para que la limitacion este documentada y no se
# descubra el dia de la sustentacion.
comprobar("LIMITACION conocida: nombre compuesto",
          normalizador.separar_nombre("MARIA JOSE PEREZ"),
          ("MARIA", "JOSE PEREZ"))


# ============================================================
#  6. CLASE DE ENCUENTRO
# ============================================================
seccion("6. normalizar_clase_encuentro")

comprobar("'URGENCIAS' -> EMER",
          normalizador.normalizar_clase_encuentro("URGENCIAS"), "EMER")
comprobar("'CONSULTA EXTERNA' -> AMB",
          normalizador.normalizar_clase_encuentro("CONSULTA EXTERNA"), "AMB")


# ============================================================
#  7. LOS TRES ANALIZADORES
# ============================================================
seccion("7. parsear_hl7 / parsear_csv / parsear_json")

HL7 = ("MSH|^~\\&|HIS|HOSP|MIRTH|FHIR|20261006210000||ADT^A01|MSG0001|P|2.5\r"
       "PID|1||98765^^^HOSP^MR||Perez^Maria||19850722|F\r"
       "PV1|1|O|CONSULTA^^^HOSP||||2002^Gomez^Carlos^M\r")

m = parsers.parsear_hl7(HL7, "IPS SINCELEJO")
comprobar("HL7: documento", m.documento, "98765")
comprobar("HL7: apellidos", m.apellidos, "Perez")
comprobar("HL7: tipo de mensaje", m.tipo_mensaje, "ADT^A01")
comprobar("HL7: el mensaje es valido", m.es_valido(), True)

CSV = ("4123456789,LAURA MEJIA ORTIZ,1988-03-25,F,2026-10-12 09:15,"
       "URGENCIAS,2,DM2,Diabetes mellitus tipo 2,GLUCOSA EN SANGRE,186,mg/dL")
m = parsers.parsear_csv(CSV, "IPS CARTAGENA")
comprobar("CSV: documento", m.documento, "4123456789")
comprobar("CSV: nombre separado", (m.nombres, m.apellidos),
          ("LAURA", "MEJIA ORTIZ"))
comprobar("CSV: triage convertido a entero", m.triage, 2)

JSN = json.dumps({"documento": "7123456789", "first_name": "JUAN",
                  "last_name": "MARTINEZ CANO", "birth_date": "1975-11-30",
                  "sex": "M", "fecha_atencion": "2026-10-18 14:40",
                  "tipo_atencion": "CONSULTA EXTERNA", "triage": "4",
                  "dx_codigo": "HTA", "dx_descripcion": "Hipertension",
                  "lab_prueba": "CREATININA", "lab_valor": "0.9",
                  "lab_unidad": "mg/dL"})
m = parsers.parsear_json(JSN, "IPS COROZAL")
comprobar("JSON: documento", m.documento, "7123456789")
comprobar("JSON: el mensaje es valido", m.es_valido(), True)


seccion("8. Los analizadores ante mensajes INVALIDOS")

# El enunciado marca como error frecuente "transformar sin
# validar". Un mensaje mal formado tiene que quedar rechazado con
# un motivo legible, no colarse a medias ni perderse.
m = parsers.parsear_hl7("", "IPS SINCELEJO")
comprobar("INVALIDO: HL7 vacio no es valido", m.es_valido(), False)
comprobar("INVALIDO: HL7 vacio da un motivo",
          m.error_validacion is not None, True)

m = parsers.parsear_csv("4123456789,LAURA MEJIA ORTIZ,1988-03-25",
                        "IPS CARTAGENA")
comprobar("INVALIDO: CSV con columnas de menos", m.es_valido(), False)

m = parsers.parsear_json("{esto no es json}", "IPS COROZAL")
comprobar("INVALIDO: JSON mal formado", m.es_valido(), False)


# ============================================================
#  9. EL BUNDLE
# ============================================================
seccion("9. construir_bundle: el resultado es FHIR R4 valido")

# construir_bundle recibe una lista de diccionarios con las
# claves 'recurso' (el JSON del recurso), 'tipo' y, si procede,
# 'si_no_existe'. Es la misma forma que arma bus.py.
bundle = normalizador.construir_bundle([
    {"recurso": normalizador.construir_patient(
        "4123456789", "LAURA", "MEJIA ORTIZ", "1988-03-25", "female",
        "IPS CARTAGENA"),
     "tipo": "Patient",
     "si_no_existe": "identifier=%s|4123456789"
                     % normalizador.SISTEMA_DOCUMENTO},
    {"recurso": normalizador.construir_encounter(
        "4123456789", "2026-10-12T09:15:00", "EMER", 2, "IPS CARTAGENA"),
     "tipo": "Encounter"},
    {"recurso": normalizador.construir_condition(
        "4123456789", "E11", "Diabetes mellitus tipo 2",
        "2026-10-12T09:15:00", "IPS CARTAGENA"),
     "tipo": "Condition"},
    {"recurso": normalizador.construir_observation(
        "4123456789", "2339-0", "GLUCOSA EN SANGRE", "186", "mg/dL",
        "2026-10-12T09:15:00", "IPS CARTAGENA"),
     "tipo": "Observation"},
])

# Si el Bundle no es JSON valido, HAPI lo rechaza antes de mirarlo.
d = json.loads(bundle)
comprobar("el Bundle es JSON bien formado", isinstance(d, dict), True)
comprobar("resourceType = Bundle", d.get("resourceType"), "Bundle")
comprobar("type = transaction", d.get("type"), "transaction")
comprobar("lleva los cuatro recursos",
          [e["resource"]["resourceType"] for e in d["entry"]],
          ["Patient", "Encounter", "Condition", "Observation"])
comprobar("Patient se crea con ifNoneExist (idempotencia)",
          "ifNoneExist" in d["entry"][0]["request"], True)
comprobar("el diagnostico va en CIE-10",
          d["entry"][2]["resource"]["code"]["coding"][0]["code"], "E11")
comprobar("el laboratorio va en LOINC",
          d["entry"][3]["resource"]["code"]["coding"][0]["code"], "2339-0")


# ============================================================
#  RESUMEN
# ============================================================
print("\n" + "=" * 66)
print(" %d pruebas pasadas, %d fallos" % (_pasadas, len(_fallos)))
if _fallos:
    for f in _fallos:
        print("   - %s" % f)
print("=" * 66)
sys.exit(1 if _fallos else 0)
