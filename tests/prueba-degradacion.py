import json, subprocess, time, urllib.request, urllib.error

BASE = "http://localhost:8001"

def pedir(ruta, metodo="GET", cuerpo=None, token=None):
    datos = None; cab = {}
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode(); cab["Content-Type"] = "application/json"
    if token: cab["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

cod, r = pedir("/api/portal/login", "POST", {"usuario":"drcarlos","clave":"medico.demo"})
tok = r["token"]

def foto(titulo):
    print("\n" + "=" * 64)
    print(" " + titulo)
    print("=" * 64)

    cod, h = pedir("/health")
    print("\n  /health  HTTP %s  estado=%s  nodos=%s"
          % (cod, h.get("estado"), h.get("nodos_arriba")))
    for d in h.get("dependencias", {}):
        print("      %-8s %s" % (d, h["dependencias"][d]))

    cod, d = pedir("/api/portal/cobertura", token=tok)
    if cod == 200:
        print("\n  Reporte de cobertura  HTTP %s   SIGUE FUNCIONANDO" % cod)
        print("      global: %s%%  (%s pacientes visibles)"
              % (d["cobertura_global"]["porcentaje"], d["cobertura_global"]["pacientes"]))
        print("      completo: %s" % d["completo"])
        for n in d["nodos_estado"]:
            print("      %-7s %s" % (n["nodo"], n["estado"]))
    else:
        print("\n  Reporte  HTTP %s  FALLO" % cod)

    cod, d = pedir("/api/portal/hc/1098765432", token=tok)
    if cod == 200:
        print("\n  Historia de Maria  HTTP %s   SIGUE FUNCIONANDO" % cod)
        print("      %d atenciones en %d sede(s), completo=%s"
              % (len(d["atenciones"]), len(d["sedes"]), d["completo"]))
        if "aviso" in d: print("      aviso: %s" % d["aviso"])
    else:
        print("\n  Historia de Maria  HTTP %s  %s" % (cod, d.get("error")))

foto("1. LAS TRES SEDES EN PIE")

print("\n\n>>> apagando pg_nodo3 (sede Corozal)...")
subprocess.run(["docker", "stop", "pg_nodo3"], capture_output=True)
time.sleep(3)
foto("2. CON UNA SEDE CAIDA - DEGRADACION PARCIAL")

print("\n\n>>> apagando tambien pg_nodo2...")
subprocess.run(["docker", "stop", "pg_nodo2"], capture_output=True)
time.sleep(3)
foto("3. CON DOS SEDES CAIDAS - SIGUE SIRVIENDO LA QUE QUEDA")

print("\n\n>>> levantando las dos sedes otra vez...")
subprocess.run(["docker", "start", "pg_nodo2", "pg_nodo3"], capture_output=True)
time.sleep(12)
foto("4. RECUPERACION AUTOMATICA, SIN REINICIAR NADA")
print()
