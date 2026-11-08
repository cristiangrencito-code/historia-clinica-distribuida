#!/usr/bin/env python3
"""
============================================================
 VERIFICADOR DE LA BITACORA DE AUDITORIA  (RF5)
============================================================

Comprueba que nadie haya tocado la bitacora.

El enunciado lo pide asi, textual:
  "El docente ... altera una fila de auditoria y el verificador
   la senala."

USO:
    python3 tests/verificar-auditoria.py
    python3 tests/verificar-auditoria.py http://localhost:8002

PARA LA DEMOSTRACION:

 1. Verificar que esta intacta:
        python3 tests/verificar-auditoria.py

 2. Alterar una fila a mano, por detras del sistema, como lo
    haria alguien que quiere borrar su rastro:
        docker exec pg_nodo1 psql -U admin -d bus_db -c \
          "UPDATE evento_auditoria SET resultado='PERMITIDO' \
           WHERE resultado='DENEGADO' AND secuencia = \
           (SELECT min(secuencia) FROM evento_auditoria \
            WHERE resultado='DENEGADO')"

 3. Volver a verificar: el verificador senala la fila exacta.

Solo usa la biblioteca estandar: urllib y json. Se puede
ejecutar desde la maquina del docente sin instalar nada.
"""

import sys
import os
import json
import urllib.request
import urllib.error


# El verificador entra por la puerta normal del sistema, con un
# usuario y un rol, no leyendo la base de datos por detras. Asi
# se demuestra tambien que la verificacion esta protegida: solo
# el rol auditor puede pedirla.
USUARIO = os.getenv("AUDITOR_USUARIO", "auditor1")
CLAVE = os.getenv("AUDITOR_CLAVE", "auditor.demo")


def pedir(url, metodo="GET", cuerpo=None, token=None):
    """Llamada HTTP sencilla. Devuelve (codigo, objeto_json)."""
    datos = None
    cabeceras = {}

    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        cabeceras["Content-Type"] = "application/json"
    if token is not None:
        cabeceras["Authorization"] = "Bearer " + token

    peticion = urllib.request.Request(url, data=datos,
                                      headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=30) as r:
            return (r.status, json.loads(r.read().decode("utf-8")))
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace")
        try:
            return (e.code, json.loads(texto))
        except Exception:
            return (e.code, {"error": texto})
    except Exception as e:
        return (0, {"error": str(e)})


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"

    print()
    print("=" * 62)
    print(" VERIFICACION DE LA BITACORA DE AUDITORIA")
    print("=" * 62)

    # ---- 1. Iniciar sesion como auditor ----
    print()
    print("1. Iniciando sesion como '%s'..." % USUARIO)
    codigo, respuesta = pedir(base + "/auth/login", "POST",
                              {"usuario": USUARIO, "clave": CLAVE})
    if codigo != 200:
        print("   FALLO (HTTP %s): %s" % (codigo, respuesta.get("error")))
        print("   Esta el bus levantado?  docker compose ps")
        return 2

    token = respuesta["token"]
    print("   sesion abierta. rol: %s" % respuesta["rol"])
    print("   permisos: %s" % ", ".join(respuesta["permisos"]))

    # ---- 2. Pedir la verificacion ----
    print()
    print("2. Recorriendo la cadena de hash...")
    codigo, r = pedir(base + "/auditoria/verificar", "GET", token=token)
    if codigo != 200:
        print("   FALLO (HTTP %s): %s" % (codigo, r))
        return 2

    print("   eventos revisados: %s" % r["eventos_revisados"])

    # ---- 3. El veredicto ----
    print()
    print("-" * 62)
    if r["integra"]:
        print(" RESULTADO: BITACORA INTEGRA")
        print(" Los %s eventos encadenan correctamente." % r["eventos_revisados"])
        print(" Ninguna fila fue modificada ni borrada.")
        print("-" * 62)
        print()
        return 0

    print(" RESULTADO: SE DETECTO MANIPULACION")
    print(" %s problema(s) en %s eventos."
          % (r["problemas_encontrados"], r["eventos_revisados"]))
    print("-" * 62)

    for p in r["problemas"]:
        print()
        print("  FILA %s  ->  %s" % (p["secuencia"], p["tipo"]))
        print("    %s" % p["explicacion"])
        if p["tipo"] == "CONTENIDO_ALTERADO":
            print("    hash guardado en la fila : %s..." % p["hash_guardado"])
            print("    hash recalculado ahora   : %s..." % p["hash_recalculado"])
            print("    contenido actual de la fila:")
            for campo in p["fila"]:
                print("      %-13s %s" % (campo + ":", p["fila"][campo]))
        else:
            print("    esperaba  : %s..." % p["esperaba"])
            print("    encontro  : %s..." % p["encontro"])

    print()
    print("-" * 62)
    print(" La cadena de hash permite senalar la fila exacta.")
    print(" Quien modifico el dato no pudo recalcular los hashes")
    print(" siguientes sin reescribir toda la bitacora.")
    print("-" * 62)
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
