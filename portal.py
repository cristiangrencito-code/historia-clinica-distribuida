r"""
============================================================
 PORTAL CLINICO  -  LAS CUATRO VISTAS POR ROL  (RF6)
============================================================

El enunciado pide cuatro vistas:

  1. PACIENTE       ve SU propia historia y nada mas
  2. ADMISIONISTA   datos administrativos, SIN diagnosticos
  3. MEDICO         la historia clinica completa de las 3 sedes
  4. REPORTE DE HC  consulta unificada + tablero de cobertura

LA IDEA CENTRAL, Y ES LA QUE HAY QUE DEFENDER:
esconder un boton no es seguridad. La vista decide que se
PINTA, pero quien decide que datos SALEN es el servidor. Cada
endpoint de aqui comprueba el token y el permiso antes de
tocar la base de datos, y si el rol no alcanza devuelve 403 y
lo anota en la bitacora. Un usuario que llame al endpoint a
mano con curl recibe exactamente el mismo 403.

TRES NIVELES DE CONTROL, no uno:

  a) AUTENTICACION   el token existe, esta firmado y vigente
  b) ROL             ese rol tiene ese permiso
  c) PERTENENCIA     un paciente solo ve SU documento

El (c) es el que suele faltar en los sistemas reales: el rol
'paciente' esta bien, pero si no se compara el documento del
token con el documento pedido, cualquier paciente lee la
historia de cualquier otro.

FILTRADO DE CAMPOS POR ROL (minimo necesario):
el admisionista recibe las atenciones pero SIN el diagnostico
ni los medicamentos. No es que la pantalla los oculte: es que
el servidor no los manda. Para admitir a alguien no hace falta
saber que enfermedad tiene.
"""

import os
import json
import urllib.request
import urllib.error

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse

import seguridad
import middleware


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HSB_URL = os.getenv("HSB_URL", "http://hsb:8002")

# Clave de servicio para hablar con el bus de servicio a
# servicio (anotar en la bitacora). Solo es alcanzable dentro de
# la red de Docker; no se expone al navegador.
CLAVE_SEDE = os.getenv("SEDE_CLAVE", "DESARROLLO-CLAVE-DE-SEDE")

# APIRouter es simplemente una lista de rutas que luego se pega
# a la app con app.include_router(). No hace nada mas.
router = APIRouter()


# ============================================================
#  AYUDANTES
# ============================================================

def llamar_hsb(ruta, metodo="GET", cuerpo=None, token=None, clave=False):
    """Llamada HTTP al bus. Devuelve (codigo, objeto)."""
    datos = None
    cabeceras = {}

    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        cabeceras["Content-Type"] = "application/json"
    if token is not None:
        cabeceras["Authorization"] = "Bearer " + token
    if clave:
        cabeceras["X-Sede-Clave"] = CLAVE_SEDE

    peticion = urllib.request.Request(HSB_URL + ruta, data=datos,
                                      headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=20) as r:
            texto = r.read().decode("utf-8")
            try:
                return (r.status, json.loads(texto))
            except Exception:
                return (r.status, {"texto": texto})
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace")
        try:
            return (e.code, json.loads(texto))
        except Exception:
            return (e.code, {"error": texto})
    except Exception as e:
        return (0, {"error": str(e)})


def anotar(usuario, rol, accion, recurso, documento_id, resultado, detalle=""):
    """
    Manda un evento a la bitacora del bus.

    POR QUE NO ESCRIBE DIRECTO EN LA TABLA:
    la cadena de hash necesita un unico escritor. La app y el bus
    son procesos distintos; si los dos escribieran, leerian el
    mismo hash_anterior y la cadena se bifurcaria. El bus es el
    unico escritor y aqui solo se le pide el apunte.

    Se usa la clave de servicio y no el token del usuario porque
    tambien hay que poder anotar los intentos de quien NO tiene
    token valido, que son justamente los que interesa registrar.
    """
    llamar_hsb("/auditoria/evento", "POST", {
        "usuario_sistema": usuario,
        "rol_sistema": rol,
        "accion": accion,
        "recurso": recurso,
        "documento_id": documento_id,
        "resultado": resultado,
        "detalle": detalle,
    }, clave=True)


def autorizar(request, accion, documento_pedido=None):
    """
    El portero. Devuelve (datos_del_token, None) o (None, error).

    Es el mismo patron explicito que en el bus:

        datos, error = autorizar(request, "VER_HC_COMPLETA")
        if error is not None:
            return error
    """
    token = seguridad.extraer_token_de_cabecera(
        request.headers.get("authorization"))

    # (a) autenticacion
    valido, resultado = seguridad.verificar_token(token)
    if not valido:
        anotar("anonimo", "?", accion, "Autenticacion", documento_pedido,
               "DENEGADO", str(resultado))
        return (None, JSONResponse({"error": "no autenticado",
                                    "motivo": resultado}, status_code=401))

    datos = resultado
    usuario = datos.get("usuario")
    rol = datos.get("rol")

    # (b) rol
    if not seguridad.puede(rol, accion):
        anotar(usuario, rol, accion, "Autorizacion", documento_pedido,
               "DENEGADO", "el rol %s no tiene el permiso %s" % (rol, accion))
        return (None, JSONResponse(
            {"error": "no autorizado",
             "motivo": "el rol %s no puede %s" % (rol, accion),
             "permisos_del_rol": seguridad.PERMISOS.get(rol, [])},
            status_code=403))

    # (c) pertenencia
    if rol == "paciente" and documento_pedido is not None:
        suyo = datos.get("documento_id")
        if suyo is None or int(documento_pedido) != int(suyo):
            anotar(usuario, rol, accion, "HistoriaClinica", documento_pedido,
                   "DENEGADO", "intento de ver la historia de otra persona")
            return (None, JSONResponse(
                {"error": "no autorizado",
                 "motivo": "solo puede consultar su propia historia"},
                status_code=403))

    return (datos, None)


def documento_valido(texto):
    """
    Convierte el documento a entero o devuelve None.

    IMPORTANTE: middleware.ejecutar_query_en_todos_los_nodos
    recibe la consulta ya armada como texto, asi que el documento
    se pega dentro de la cadena SQL. Pasarlo por int() primero es
    lo que impide una inyeccion: si no es un numero, no se
    construye ninguna consulta.
    """
    try:
        return int(str(texto).strip())
    except Exception:
        return None


# ============================================================
#  CONSULTA UNIFICADA DE LA HISTORIA CLINICA  (RF4 + RF6)
# ============================================================

def consultar_historia(documento):
    """
    Arma la historia clinica de un paciente juntando los tres
    nodos, y dice cuales respondieron.

    POR QUE PREGUNTA A LOS TRES SI EL PACIENTE VIVE EN UNO:
    quien consulta no sabe en que nodo esta el documento, y el
    sistema no deberia obligarle a saberlo. La fragmentacion es
    un detalle de almacenamiento, no algo que el usuario tenga
    que entender. El middleware pregunta a los tres, descarta los
    que no responden y devuelve lo que haya.

    Y ESO ES LA DEGRADACION PARCIAL DEL RNF: si una sede se cae,
    esta consulta NO falla. Devuelve los datos de las que siguen
    en pie y marca la caida como DOWN, para que la vista pueda
    avisar de que lo que se esta viendo esta incompleto.
    """
    datos = {"documento_id": documento}

    # --- 1. El paciente ---
    q = ("SELECT documento_id, tipo_documento, nombre_completo, "
         "       fecha_nacimiento, edad, sexo, genero, ocupacion, "
         "       municipio_residencia, zona_residencia, fhir_patient_id "
         "FROM usuario WHERE documento_id = %d" % documento)
    r = middleware.ejecutar_query_en_todos_los_nodos(q)
    datos["nodos_estado"] = r["nodos_estado"]
    datos["paciente"] = r["resultados"][0] if len(r["resultados"]) > 0 else None

    # --- 2. Las atenciones, con diagnostico y egreso ---
    q = ("SELECT a.atencion_id, a.entidad_salud, a.fecha_ingreso, "
         "       a.entorno_atencion, a.via_ingreso, a.causa_atencion, "
         "       a.clasificacion_triage, "
         "       d.tipo_diagnostico_ingreso, d.diagnostico_ingreso, "
         "       d.tipo_diagnostico_egreso, d.diagnostico_egreso, "
         "       e.fecha_salida, e.condicion_salida, e.alergias, "
         "       e.antecedente_familiar, e.responsable_egreso "
         "FROM atencion a "
         "LEFT JOIN diagnostico d ON d.atencion_id = a.atencion_id "
         "LEFT JOIN egreso e      ON e.atencion_id = a.atencion_id "
         "WHERE a.documento_id = %d "
         "ORDER BY a.fecha_ingreso" % documento)
    r = middleware.ejecutar_query_en_todos_los_nodos(q)
    datos["atenciones"] = r["resultados"]

    # --- 3. Los medicamentos ---
    # tecnologia_salud no tiene documento_id, asi que se llega a
    # el por la atencion.
    q = ("SELECT t.atencion_id, t.descripcion_medicamento, t.dosis, "
         "       t.via_administracion, t.frecuencia, t.dias_tratamiento, "
         "       t.finalidad_tecnologia, p.nombre AS profesional, "
         "       p.especialidad "
         "FROM tecnologia_salud t "
         "JOIN atencion a ON a.atencion_id = t.atencion_id "
         "LEFT JOIN profesional_salud p "
         "       ON p.id_personal_salud = t.id_personal_salud "
         "WHERE a.documento_id = %d" % documento)
    r = middleware.ejecutar_query_en_todos_los_nodos(q)
    datos["medicamentos"] = r["resultados"]

    # --- 4. Resumen por sede ---
    # La fragmentacion reparte por DOCUMENTO, pero la historia
    # esta repartida por SEDE (atencion.entidad_salud). Son dos
    # cosas distintas y conviene verlo junto: este bloque es la
    # prueba de que la vista unificada junta las 3 sedes.
    sedes = {}
    for a in datos["atenciones"]:
        nombre = a.get("entidad_salud") or "SIN SEDE"
        if nombre not in sedes:
            sedes[nombre] = 0
        sedes[nombre] = sedes[nombre] + 1

    lista_sedes = []
    for nombre in sedes:
        lista_sedes.append({"sede": nombre, "atenciones": sedes[nombre]})
    datos["sedes"] = lista_sedes

    # --- 5. Aviso de resultado incompleto ---
    caidos = []
    for n in datos["nodos_estado"]:
        if n["estado"] != "UP":
            caidos.append(n["nodo"])

    datos["completo"] = len(caidos) == 0
    if len(caidos) > 0:
        datos["aviso"] = ("Resultado PARCIAL: no respondieron %s. "
                          "Puede faltar informacion."
                          % ", ".join(caidos))

    return datos


def quitar_datos_clinicos(historia):
    """
    Deja la historia sin informacion clinica, para el
    admisionista.

    Es el principio del minimo necesario: el admisionista
    necesita saber que el paciente estuvo, cuando y por que
    puerta entro, para admitirlo bien. No necesita el
    diagnostico, ni los medicamentos, ni las alergias.

    Se construye una copia NUEVA con los campos permitidos, en
    vez de borrar los prohibidos de la original. Asi, si manana
    alguien anade una columna clinica a la consulta, no se filtra
    sola: habria que anadirla aqui a mano.
    """
    atenciones = []
    for a in historia.get("atenciones", []):
        atenciones.append({
            "atencion_id": a.get("atencion_id"),
            "entidad_salud": a.get("entidad_salud"),
            "fecha_ingreso": a.get("fecha_ingreso"),
            "entorno_atencion": a.get("entorno_atencion"),
            "via_ingreso": a.get("via_ingreso"),
            "clasificacion_triage": a.get("clasificacion_triage"),
            "fecha_salida": a.get("fecha_salida"),
            "condicion_salida": a.get("condicion_salida"),
        })

    paciente = historia.get("paciente")
    copia = {
        "documento_id": historia.get("documento_id"),
        "paciente": paciente,
        "atenciones": atenciones,
        "sedes": historia.get("sedes", []),
        "medicamentos": [],
        "nodos_estado": historia.get("nodos_estado", []),
        "completo": historia.get("completo", True),
        "filtrado": ("vista administrativa: sin diagnosticos, "
                     "medicamentos ni alergias"),
    }
    if "aviso" in historia:
        copia["aviso"] = historia["aviso"]
    return copia


# ============================================================
#  API DEL PORTAL
# ============================================================

@router.post("/api/portal/login")
async def portal_login(request: Request):
    """
    Reenvia el inicio de sesion al bus, que es quien tiene la
    tabla de usuarios y quien firma los tokens.

    La app no comprueba claves: solo VALIDA tokens ya firmados
    (ver seguridad.py). Hay un unico sitio donde se decide quien
    entra, y es el bus.
    """
    try:
        cuerpo = await request.json()
    except Exception:
        return JSONResponse({"error": "se esperaba JSON"}, status_code=400)

    codigo, respuesta = llamar_hsb("/auth/login", "POST", cuerpo)
    if codigo == 0:
        return JSONResponse(
            {"error": "el bus no responde", "detalle": respuesta.get("error")},
            status_code=503)
    return JSONResponse(respuesta, status_code=codigo)


@router.get("/api/portal/yo")
def portal_yo(request: Request):
    """Lo que dice el token. La vista lo usa para saber que pintar."""
    token = seguridad.extraer_token_de_cabecera(
        request.headers.get("authorization"))
    valido, datos = seguridad.verificar_token(token)
    if not valido:
        return JSONResponse({"error": "no autenticado", "motivo": datos},
                            status_code=401)
    return {
        "usuario": datos.get("usuario"),
        "rol": datos.get("rol"),
        "documento_id": datos.get("documento_id"),
        "permisos": seguridad.PERMISOS.get(datos.get("rol"), []),
        "caduca_en": datos.get("exp"),
    }


@router.get("/api/portal/hc/{documento}")
def portal_hc(request: Request, documento: str):
    """
    La historia clinica unificada. El MISMO endpoint para los
    tres roles que pueden verla, con tres resultados distintos:

      medico       -> todo
      paciente     -> todo, pero SOLO de su propio documento
      admisionista -> sin diagnosticos ni medicamentos
      auditor      -> 403, no tiene nada que hacer aqui

    Tener un solo endpoint y no tres evita el error clasico de
    arreglar el control en una copia y olvidarlo en las otras.
    """
    doc = documento_valido(documento)
    if doc is None:
        return JSONResponse({"error": "el documento debe ser numerico"},
                            status_code=400)

    token = seguridad.extraer_token_de_cabecera(
        request.headers.get("authorization"))
    valido, datos_token = seguridad.verificar_token(token)
    if not valido:
        anotar("anonimo", "?", "VER_HC", "HistoriaClinica", doc,
               "DENEGADO", str(datos_token))
        return JSONResponse({"error": "no autenticado",
                             "motivo": datos_token}, status_code=401)

    rol = datos_token.get("rol")

    # Que permiso hace falta depende del rol que pregunta.
    if rol == "paciente":
        permiso = "VER_HC_PROPIA"
    elif rol == "admisionista":
        permiso = "VER_DATOS_ADMINISTRATIVOS"
    else:
        permiso = "VER_HC_COMPLETA"

    datos, error = autorizar(request, permiso, doc)
    if error is not None:
        return error

    historia = consultar_historia(doc)

    if historia["paciente"] is None:
        anotar(datos.get("usuario"), rol, "VER_HC", "HistoriaClinica", doc,
               "PERMITIDO", "no existe el paciente")
        return JSONResponse(
            {"error": "no se encontro el paciente",
             "documento_id": doc,
             "nodos_estado": historia["nodos_estado"],
             "completo": historia["completo"]},
            status_code=404)

    if rol == "admisionista":
        historia = quitar_datos_clinicos(historia)

    historia["visto_por"] = {"usuario": datos.get("usuario"), "rol": rol}

    anotar(datos.get("usuario"), rol, "VER_HC", "HistoriaClinica", doc,
           "PERMITIDO",
           "%d atenciones en %d sede(s)%s"
           % (len(historia.get("atenciones", [])),
              len(historia.get("sedes", [])),
              "" if historia.get("completo") else " (resultado parcial)"))

    return historia


@router.get("/api/portal/buscar")
def portal_buscar(request: Request, nombre: str = "", documento: str = ""):
    """
    Busca pacientes en los tres nodos por nombre o documento.
    La usan el admisionista y el medico; el paciente no busca a
    nadie, solo se ve a si mismo.
    """
    datos, error = autorizar(request, "BUSCAR_PACIENTE")
    if error is not None:
        return error

    condiciones = []

    if documento.strip() != "":
        doc = documento_valido(documento)
        if doc is None:
            return JSONResponse({"error": "el documento debe ser numerico"},
                                status_code=400)
        condiciones.append("documento_id = %d" % doc)

    if nombre.strip() != "":
        # Se filtran las comillas y los caracteres con los que se
        # cierra una cadena SQL. El nombre es texto libre, asi que
        # es la entrada mas expuesta de todo el portal.
        limpio = ""
        for c in nombre.upper():
            if c.isalnum() or c == " ":
                limpio = limpio + c
        if limpio.strip() == "":
            return JSONResponse({"error": "nombre no valido"}, status_code=400)
        condiciones.append("nombre_completo LIKE '%%%s%%'" % limpio)

    if len(condiciones) == 0:
        return JSONResponse({"error": "indique nombre o documento"},
                            status_code=400)

    q = ("SELECT documento_id, tipo_documento, nombre_completo, edad, sexo, "
         "       municipio_residencia, fhir_patient_id "
         "FROM usuario WHERE " + " AND ".join(condiciones) + " LIMIT 50")

    r = middleware.ejecutar_query_en_todos_los_nodos(q)

    anotar(datos.get("usuario"), datos.get("rol"), "BUSCAR_PACIENTE",
           "Usuario", None, "PERMITIDO",
           "%d resultado(s)" % len(r["resultados"]))

    return {
        "resultados": r["resultados"],
        "nodos_estado": r["nodos_estado"],
        "completo": all(n["estado"] == "UP" for n in r["nodos_estado"]),
    }


# ============================================================
#  TABLERO DE COBERTURA  (RF6)
#
#  El enunciado pide "un tablero con el porcentaje de historias
#  normalizadas a FHIR por sede".
#
#  COMO SE MIDE: usuario.fhir_patient_id. Esa columna esta vacia
#  mientras el paciente solo existe en la base local, y el bus la
#  rellena cuando consigue crear el Patient en HAPI FHIR. O sea
#  que no es un contador aparte que haya que mantener: es la
#  consecuencia de que la migracion de verdad ocurrio. Un
#  contador se puede desincronizar; esto no.
# ============================================================

@router.get("/api/portal/cobertura")
def portal_cobertura(request: Request):
    """Datos del tablero: cobertura FHIR, estado de nodos y metricas."""
    datos, error = autorizar(request, "VER_COBERTURA")
    if error is not None:
        return error

    # --- Cobertura global y por nodo ---
    q = ("SELECT count(*) AS total, "
         "       count(fhir_patient_id) AS con_fhir "
         "FROM usuario")
    r = middleware.ejecutar_query_en_todos_los_nodos(q)

    total = 0
    con_fhir = 0
    por_nodo = []
    i = 0
    for fila in r["resultados"]:
        total = total + int(fila["total"])
        con_fhir = con_fhir + int(fila["con_fhir"])
        nombre = r["nodos_estado"][i]["nodo"] if i < len(r["nodos_estado"]) else "?"
        porcentaje = 0.0
        if int(fila["total"]) > 0:
            porcentaje = round(100.0 * int(fila["con_fhir"]) / int(fila["total"]), 2)
        por_nodo.append({"nodo": nombre,
                         "pacientes": int(fila["total"]),
                         "con_fhir": int(fila["con_fhir"]),
                         "porcentaje": porcentaje})
        i = i + 1

    # --- Cobertura por SEDE ---
    # La sede no esta en usuario sino en atencion.entidad_salud,
    # asi que hay que ir por ahi. count(DISTINCT) porque un
    # paciente puede tener varias atenciones en la misma sede y
    # no debe contarse dos veces.
    q = ("SELECT a.entidad_salud AS sede, "
         "       count(DISTINCT a.documento_id) AS pacientes, "
         "       count(DISTINCT u.fhir_patient_id) AS con_fhir, "
         "       count(a.atencion_id) AS atenciones "
         "FROM atencion a "
         "JOIN usuario u ON u.documento_id = a.documento_id "
         "GROUP BY a.entidad_salud "
         "ORDER BY a.entidad_salud")
    r2 = middleware.ejecutar_query_en_todos_los_nodos(q)

    # Un mismo nombre de sede puede venir de varios nodos (la
    # sede no coincide con el nodo), asi que hay que sumarlos.
    acumulado = {}
    for fila in r2["resultados"]:
        sede = fila["sede"] or "SIN SEDE"
        if sede not in acumulado:
            acumulado[sede] = {"pacientes": 0, "con_fhir": 0, "atenciones": 0}
        acumulado[sede]["pacientes"] += int(fila["pacientes"])
        acumulado[sede]["con_fhir"] += int(fila["con_fhir"])
        acumulado[sede]["atenciones"] += int(fila["atenciones"])

    por_sede = []
    for sede in sorted(acumulado.keys()):
        a = acumulado[sede]
        porcentaje = 0.0
        if a["pacientes"] > 0:
            porcentaje = round(100.0 * a["con_fhir"] / a["pacientes"], 2)
        por_sede.append({"sede": sede, "pacientes": a["pacientes"],
                         "con_fhir": a["con_fhir"],
                         "atenciones": a["atenciones"],
                         "porcentaje": porcentaje})

    # --- Metricas del bus ---
    metricas = {}
    codigo, cuerpo = llamar_hsb("/metrics")
    if codigo == 200 and "texto" in cuerpo:
        for linea in cuerpo["texto"].split("\n"):
            if linea.startswith("#") or linea.strip() == "":
                continue
            partes = linea.split(" ")
            if len(partes) == 2:
                metricas[partes[0]] = partes[1]

    porcentaje_global = 0.0
    if total > 0:
        porcentaje_global = round(100.0 * con_fhir / total, 2)

    anotar(datos.get("usuario"), datos.get("rol"), "VER_COBERTURA",
           "Tablero", None, "PERMITIDO",
           "cobertura global %.2f%%" % porcentaje_global)

    return {
        "cobertura_global": {
            "pacientes": total,
            "con_fhir": con_fhir,
            "sin_fhir": total - con_fhir,
            "porcentaje": porcentaje_global,
        },
        "por_nodo": por_nodo,
        "por_sede": por_sede,
        "nodos_estado": r["nodos_estado"],
        "metricas_bus": metricas,
        "completo": all(n["estado"] == "UP" for n in r["nodos_estado"]),
    }


# ============================================================
#  LAS CUATRO VISTAS
#
#  Las cuatro sirven el MISMO fichero HTML. El fichero mira la
#  direccion para saber que vista pintar y pide al servidor los
#  datos que esa vista necesita.
#
#  No se comprueba el rol al servir la pagina, y es a proposito:
#  un GET de navegador no lleva la cabecera Authorization, asi
#  que el token no esta disponible todavia. Da igual, porque la
#  pagina vacia no tiene ningun dato; en cuanto pide datos, el
#  servidor aplica el control. Por eso el control esta en los
#  endpoints y no en las paginas.
# ============================================================

def servir_portal():
    ruta = os.path.join(BASE_DIR, "templates", "portal.html")
    with open(ruta, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@router.get("/login", response_class=HTMLResponse)
def vista_login():
    return servir_portal()


@router.get("/vista/paciente", response_class=HTMLResponse)
def vista_paciente():
    return servir_portal()


@router.get("/vista/admisionista", response_class=HTMLResponse)
def vista_admisionista():
    return servir_portal()


@router.get("/vista/medico", response_class=HTMLResponse)
def vista_medico():
    return servir_portal()


@router.get("/vista/reporte", response_class=HTMLResponse)
def vista_reporte():
    return servir_portal()


# ============================================================
#  OBSERVABILIDAD DE LA APP  (RNF)
#  El enunciado pide /health y /metrics en CADA servicio.
# ============================================================

@router.get("/health")
def health():
    """
    Estado de la app y de sus dependencias.

    Devuelve 'degradado' (503) y no 'caido' cuando falla una
    parte: con dos de tres nodos en pie la app sigue sirviendo
    historias, solo que incompletas. Un sistema distribuido no
    esta vivo o muerto, tiene grados.
    """
    estado = {"servicio": "app", "estado": "ok", "dependencias": {}}

    if seguridad.usando_secreto_de_desarrollo():
        estado["aviso_seguridad"] = ("JWT_SECRETO no configurado: se esta "
                                     "usando el secreto de desarrollo")

    arriba = 0
    r = middleware.ejecutar_query_en_todos_los_nodos("SELECT 1 AS ok")
    for n in r["nodos_estado"]:
        estado["dependencias"][n["nodo"]] = n["estado"].lower()
        if n["estado"] == "UP":
            arriba = arriba + 1

    if arriba == 0:
        estado["estado"] = "caido"
    elif arriba < len(r["nodos_estado"]):
        estado["estado"] = "degradado"

    # El bus responde 503 cuando el esta degradado (por ejemplo si
    # HAPI no contesta), pero 503 NO quiere decir que este caido:
    # quiere decir que contesto para avisar de que algo le falla.
    # Caido es cuando no contesta nada, y eso aqui es codigo 0.
    # Confundir las dos cosas daba el absurdo de ver "hsb: caido"
    # junto a una respuesta suya.
    codigo, cuerpo = llamar_hsb("/health")
    if codigo == 0:
        estado["dependencias"]["hsb"] = "caido: no responde"
        if estado["estado"] == "ok":
            estado["estado"] = "degradado"
    else:
        suyo = cuerpo.get("estado", "desconocido")
        estado["dependencias"]["hsb"] = suyo
        if suyo != "ok" and estado["estado"] == "ok":
            estado["estado"] = "degradado"

    estado["nodos_arriba"] = "%d de %d" % (arriba, len(r["nodos_estado"]))

    return JSONResponse(estado,
                        status_code=200 if estado["estado"] == "ok" else 503)


@router.get("/metrics")
def metrics():
    """Metricas de la app en formato de texto, estilo Prometheus."""
    lineas = []

    r = middleware.ejecutar_query_en_todos_los_nodos("SELECT 1 AS ok")
    arriba = 0
    for n in r["nodos_estado"]:
        vivo = 1 if n["estado"] == "UP" else 0
        arriba = arriba + vivo
        lineas.append('app_nodo_arriba{nodo="%s"} %d' % (n["nodo"], vivo))

    lineas.insert(0, "# HELP app_nodo_arriba 1 si el nodo responde, 0 si no")
    lineas.append("# HELP app_nodos_arriba Nodos que responden")
    lineas.append("app_nodos_arriba %d" % arriba)
    lineas.append("app_nodos_totales %d" % len(r["nodos_estado"]))

    q = ("SELECT count(*) AS total, count(fhir_patient_id) AS con_fhir "
         "FROM usuario")
    r2 = middleware.ejecutar_query_en_todos_los_nodos(q)
    total = 0
    con_fhir = 0
    for fila in r2["resultados"]:
        total = total + int(fila["total"])
        con_fhir = con_fhir + int(fila["con_fhir"])

    porcentaje = 0.0
    if total > 0:
        porcentaje = round(100.0 * con_fhir / total, 2)

    lineas.append("# HELP app_pacientes_total Pacientes en los nodos vivos")
    lineas.append("app_pacientes_total %d" % total)
    lineas.append("app_pacientes_con_fhir %d" % con_fhir)
    lineas.append("# HELP app_cobertura_fhir_porcentaje Historias normalizadas")
    lineas.append("app_cobertura_fhir_porcentaje %s" % porcentaje)

    return PlainTextResponse("\n".join(lineas) + "\n")
