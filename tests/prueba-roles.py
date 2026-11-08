#!/usr/bin/env python3
"""
============================================================
 PRUEBA DE AUTENTICACION Y AUTORIZACION POR ROL  (RF5)
============================================================

El enunciado pide "evidencia de accesos permitidos y
denegados". Este script los produce: inicia sesion con los
cuatro roles y, con cada uno, intenta entrar a lo que le
corresponde y a lo que no.

    python3 tests/prueba-roles.py

Las claves de los usuarios de demostracion estan en
infra/bus-schema.sql, junto a la tabla usuario_sistema.
Son sinteticas y solo valen para esta demo.

Solo usa la biblioteca estandar: urllib y json.
"""

import json
import urllib.request
import urllib.error


BASE = "http://localhost:8002"

def pedir(ruta, metodo="GET", cuerpo=None, token=None):
    datos = None; cab = {}
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode(); cab["Content-Type"] = "application/json"
    if token: cab["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}

def login(u, c):
    cod, r = pedir("/auth/login", "POST", {"usuario": u, "clave": c})
    return r.get("token"), r, cod

print("=" * 66)
print(" PRUEBA DE AUTENTICACION Y AUTORIZACION POR ROL  (RF5)")
print("=" * 66)

print("\n--- A. AUTENTICACION ---\n")

tok_mal, r, cod = login("auditor1", "clave-equivocada")
print("  clave incorrecta           HTTP %s  %s" % (cod, r.get("error")))
tok_inex, r, cod = login("no-existe", "cualquiera")
print("  usuario inexistente        HTTP %s  %s" % (cod, r.get("error")))
print("    (el mismo mensaje en los dos casos: no se filtra que usuarios existen)")

tokens = {}
for u, c in [("maria","maria.demo"), ("admision1","admision.demo"),
             ("drcarlos","medico.demo"), ("auditor1","auditor.demo")]:
    t, r, cod = login(u, c)
    tokens[u] = t
    print("  %-11s %-14s HTTP %s  token emitido" % (u, "("+r.get("rol","?")+")", cod))

print("\n  sin token:                 HTTP %s" % pedir("/auditoria")[0])
print("  token alterado:            HTTP %s" % pedir("/auditoria", token=tokens["auditor1"][:-4]+"AAAA")[0])

print("\n--- B. AUTORIZACION: quien puede ver la BITACORA ---\n")
for u in ["maria", "admision1", "drcarlos", "auditor1"]:
    cod, r = pedir("/auditoria?limite=3", token=tokens[u])
    v = "PERMITIDO" if cod == 200 else "DENEGADO  -> " + str(r.get("motivo",""))[:48]
    print("  %-11s HTTP %s  %s" % (u, cod, v))

print("\n--- C. AUTORIZACION: quien puede VERIFICAR la cadena ---\n")
for u in ["drcarlos", "auditor1"]:
    cod, r = pedir("/auditoria/verificar", token=tokens[u])
    v = "PERMITIDO" if cod == 200 else "DENEGADO  -> " + str(r.get("motivo",""))[:48]
    print("  %-11s HTTP %s  %s" % (u, cod, v))

print("\n--- D. AUTORIZACION: quien puede INGESTAR ---\n")
for u in ["drcarlos", "maria"]:
    cod, r = pedir("/ingesta/csv?sede=sede2", "POST", None, tokens[u])
    print("  %-11s HTTP %s  %s" % (u, cod, "PERMITIDO" if cod==200 else "DENEGADO"))

print()
