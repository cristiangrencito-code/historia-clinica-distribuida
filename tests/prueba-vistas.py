import json, urllib.request, urllib.error

BASE = "http://localhost:8001"

def pedir(ruta, metodo="GET", cuerpo=None, token=None):
    datos = None; cab = {}
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode(); cab["Content-Type"] = "application/json"
    if token: cab["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

T = {}
print("=" * 70)
print(" PORTAL CLINICO - LAS CUATRO VISTAS POR ROL  (RF6)")
print("=" * 70)
print("\n--- Inicio de sesion de los cuatro roles ---\n")
for u, c in [("maria","maria.demo"),("admision1","admision.demo"),
             ("drcarlos","medico.demo"),("auditor1","auditor.demo")]:
    cod, r = pedir("/api/portal/login", "POST", {"usuario": u, "clave": c})
    T[u] = r.get("token")
    print("  %-11s HTTP %s  rol=%-13s doc=%s" % (u, cod, r.get("rol"), r.get("documento_id")))

print("\n--- HISTORIA CLINICA de Maria (1098765432) con cada rol ---\n")
for u in ["maria","admision1","drcarlos","auditor1"]:
    cod, r = pedir("/api/portal/hc/1098765432", token=T[u])
    if cod != 200:
        print("  %-11s HTTP %s  DENEGADO: %s" % (u, cod, str(r.get("motivo"))[:46]))
        continue
    at = r.get("atenciones", [])
    dx = sum(1 for a in at if a.get("diagnostico_ingreso"))
    print("  %-11s HTTP %s  PERMITIDO  atenciones=%d sedes=%d diagnosticos=%d medicamentos=%d"
          % (u, cod, len(at), len(r.get("sedes",[])), dx, len(r.get("medicamentos",[]))))
    if r.get("filtrado"):
        print("  %-11s             filtrado -> %s" % ("", r["filtrado"]))

print("\n--- PERTENENCIA: Maria pide la historia de OTRO paciente ---\n")
cod, r = pedir("/api/portal/hc/1033445566", token=T["maria"])
print("  maria -> doc 1033445566   HTTP %s  %s" % (cod, r.get("motivo")))
cod, r = pedir("/api/portal/hc/1033445566", token=T["drcarlos"])
print("  drcarlos -> doc 1033445566 HTTP %s  %s" % (cod, "PERMITIDO" if cod==200 else r.get("motivo")))

print("\n--- BUSQUEDA ---\n")
for u in ["admision1","drcarlos","maria"]:
    cod, r = pedir("/api/portal/buscar?nombre=MARIA", token=T[u])
    v = "%d resultado(s)" % len(r.get("resultados",[])) if cod==200 else "DENEGADO: "+str(r.get("motivo"))[:40]
    print("  %-11s HTTP %s  %s" % (u, cod, v))

print("\n--- TABLERO DE COBERTURA ---\n")
for u in ["drcarlos","auditor1","admision1","maria"]:
    cod, r = pedir("/api/portal/cobertura", token=T[u])
    v = "global %s%%" % r["cobertura_global"]["porcentaje"] if cod==200 else "DENEGADO"
    print("  %-11s HTTP %s  %s" % (u, cod, v))

cod, r = pedir("/api/portal/cobertura", token=T["auditor1"])
if cod == 200:
    print("\n  por sede:")
    for s in r["por_sede"]:
        print("    %-16s pacientes=%d atenciones=%d fhir=%d  %s%%"
              % (s["sede"], s["pacientes"], s["atenciones"], s["con_fhir"], s["porcentaje"]))
    print("  por nodo:")
    for n in r["por_nodo"]:
        print("    %-7s pacientes=%d fhir=%d  %s%%" % (n["nodo"], n["pacientes"], n["con_fhir"], n["porcentaje"]))
    print("  nodos:", ", ".join("%s=%s" % (n["nodo"], n["estado"]) for n in r["nodos_estado"]))
print()
