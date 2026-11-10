"""
============================================================
 HSB - HEALTH SERVICE BUS  (RF3)
============================================================

El corazon del parcial. Recibe mensajes de las 3 sedes en 3
formatos distintos y los lleva, de forma fiable, hasta HAPI FHIR
y hasta el nodo fragmentado que le corresponde al paciente.

LA CADENA DE PROCESAMIENTO:

    recepcion -> idempotencia -> validacion -> transformacion
              -> enrutamiento por documento -> entrega -> auditoria

LAS TRES GARANTIAS QUE LO HACEN UN BUS Y NO UN SCRIPT:

  1. IDEMPOTENCIA
     Cada mensaje se identifica por el SHA-256 de su contenido.
     La restriccion UNIQUE de mensaje_bus.hash_mensaje impide
     procesarlo dos veces. La garantia vive en la base de datos,
     no en el codigo: entre un SELECT y un INSERT podria colarse
     otro hilo con el mismo mensaje.

  2. REINTENTOS CON RETROCESO EXPONENCIAL
     Si HAPI esta caido, el mensaje NO se pierde: queda FALLIDO
     con una fecha de proximo intento. Un hilo en segundo plano
     lo reintenta esperando cada vez mas (2s, 4s, 8s, 16s, 32s).
     Esperar cada vez mas evita martillar un servicio que ya esta
     en problemas.

  3. COLA DE MENSAJES MUERTOS (DLQ)
     Tras agotar los intentos el mensaje pasa a MUERTO, con el
     motivo guardado. No se borra ni se reintenta para siempre:
     queda para revision manual.

DIFERENCIA ENTRE RECHAZADO Y MUERTO (importante para la sustentacion):
  RECHAZADO = el mensaje esta mal (fecha invalida, falta el
              documento). Reintentarlo daria el mismo error, asi
              que NO se reintenta.
  MUERTO    = el mensaje estaba bien pero el destino fallo y se
              agotaron los reintentos. Es un problema de
              infraestructura, no de contenido.
"""

import os
import time
import json
import threading
import hashlib
import datetime
import urllib.request
import urllib.error

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

import normalizador
import parsers
import seguridad


# ============================================================
#  CONFIGURACION
# ============================================================

HAPI_URL = os.getenv("HAPI_URL", "http://hapi_fhir_server:8080/fhir")

BUS_DB = {
    "host": os.getenv("BUS_DB_HOST", "pg_nodo1"),
    "port": int(os.getenv("BUS_DB_PORT", "5432")),
    "user": os.getenv("BUS_DB_USER", "admin"),
    "password": os.getenv("BUS_DB_PASSWORD", "admin"),
    "dbname": os.getenv("BUS_DB_NAME", "bus_db"),
}

# Los tres nodos fragmentados, con el mismo criterio de reparto
# que usa la app del profesor (_nodo_por_documento).
NODOS = [
    {"nombre": "nodo1", "host": "pg_nodo1", "port": 5432,
     "desde": 0,           "hasta": 4000000000},
    {"nombre": "nodo2", "host": "pg_nodo2", "port": 5432,
     "desde": 4000000000,  "hasta": 7000000000},
    {"nombre": "nodo3", "host": "pg_nodo3", "port": 5432,
     "desde": 7000000000,  "hasta": 10**18},
]
NODO_USER = os.getenv("NODO_DB_USER", "admin")
NODO_PASS = os.getenv("NODO_DB_PASSWORD", "admin")
NODO_DB = os.getenv("NODO_DB_NAME", "historia_clinica")

# Credencial de maquina para las sedes y para Mirth. Un sistema
# automatico no puede escribir una clave en un formulario, asi
# que se autentica con una clave de servicio fija en la cabecera
# X-Sede-Clave. Es lo mismo que hace una API key. El valor real
# va en .env; el de aqui es de desarrollo.
CLAVE_SEDE = os.getenv("SEDE_CLAVE", "DESARROLLO-CLAVE-DE-SEDE")

MAX_INTENTOS = int(os.getenv("HSB_MAX_INTENTOS", "5"))
ESPERA_BASE = int(os.getenv("HSB_ESPERA_BASE", "2"))   # segundos

# A que sede corresponde cada puerto/ruta de entrada
SEDES = {
    "sede1": "IPS SINCELEJO",
    "sede2": "IPS CARTAGENA",
    "sede3": "IPS COROZAL",
}


app = FastAPI(title="HSB - Health Service Bus",
              description="Bus de integracion HL7 v2 / CSV / JSON -> FHIR R4")


# ============================================================
#  AYUDANTES DE BASE DE DATOS
# ============================================================

def conectar_bus():
    """Conexion a bus_db, donde viven mensaje_bus y evento_auditoria."""
    return psycopg2.connect(**BUS_DB)


def nodo_por_documento(documento_id):
    """
    Decide en QUE NODO vive un paciente, por el rango de su documento.

    Esta es la fragmentacion horizontal del RF4. El criterio tiene
    que ser EXACTAMENTE el mismo que usa la app principal, o los
    datos se escribirian en un nodo y se buscarian en otro.
    """
    doc = int(documento_id)
    for n in NODOS:
        if n["desde"] <= doc < n["hasta"]:
            return n
    return NODOS[-1]


def conectar_nodo(documento_id):
    """Abre conexion al nodo que le toca a ese documento."""
    n = nodo_por_documento(documento_id)
    con = psycopg2.connect(host=n["host"], port=n["port"],
                           user=NODO_USER, password=NODO_PASS,
                           dbname=NODO_DB)
    return con, n["nombre"]


def calcular_hash(contenido):
    """
    SHA-256 del contenido del mensaje. ES la clave de idempotencia.

    Se usa el CONTENIDO y no el id de control del mensaje (MSH-10)
    porque algunos sistemas legados reutilizan los ids al
    reiniciarse, y entonces un mensaje nuevo se confundiria con
    uno viejo y se perderia.
    """
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


# ============================================================
#  AUDITORIA ENCADENADA POR HASH  (RF5)
# ============================================================

_candado_auditoria = threading.Lock()


def registrar_auditoria(usuario, rol, accion, recurso,
                        documento_id, resultado, detalle=""):
    """
    Escribe un evento de auditoria encadenado al anterior.

    COMO FUNCIONA LA CADENA:
      hash_actual = SHA-256( contenido_del_evento + hash_anterior )

    Si alguien modifica una fila vieja, su hash deja de cuadrar con
    el que guardo el evento siguiente, y el verificador detecta
    exactamente en que punto se rompio. Es el principio de una
    cadena de bloques, sin necesidad de una blockchain.

    El candado (Lock) serializa la escritura: dos eventos a la vez
    podrian leer el mismo hash_anterior y bifurcar la cadena.
    """
    with _candado_auditoria:
        con = None
        try:
            con = conectar_bus()
            cur = con.cursor()

            # 1. Leer el hash del ultimo evento
            cur.execute("SELECT hash_actual FROM evento_auditoria "
                        "ORDER BY secuencia DESC LIMIT 1")
            fila = cur.fetchone()
            hash_anterior = fila[0] if fila else "GENESIS"

            # 2. Construir el contenido del evento nuevo
            #
            # La hora se calcula AQUI y se guarda explicitamente en
            # el INSERT. Antes la columna ts se llenaba sola con el
            # DEFAULT now() de PostgreSQL mientras el hash se
            # calculaba con la hora de Python: dos relojes y dos
            # instantes distintos, asi que el verificador no podia
            # recalcular el hash y marcaba como alteradas filas que
            # nadie habia tocado.
            #
            # REGLA GENERAL, y es la leccion del fallo: el hash
            # tiene que calcularse sobre EXACTAMENTE los mismos
            # datos que quedan guardados. Si un campo lo rellena la
            # base de datos, no puede entrar en la firma.
            ahora = datetime.datetime.now()
            contenido = "|".join([
                ahora.isoformat(), str(usuario), str(rol), str(accion),
                str(recurso), str(documento_id), str(resultado), str(detalle)
            ])

            # 3. Encadenar: el hash incluye el del evento anterior
            hash_actual = hashlib.sha256(
                (contenido + hash_anterior).encode("utf-8")).hexdigest()

            cur.execute(
                "INSERT INTO evento_auditoria "
                "(ts, usuario, rol, accion, recurso, documento_id, resultado, "
                " detalle, hash_anterior, hash_actual) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (ahora, usuario, rol, accion, recurso, documento_id,
                 resultado, detalle, hash_anterior, hash_actual))
            con.commit()
            cur.close()
            return hash_actual
        except Exception as e:
            print("ERROR registrando auditoria:", e)
            return None
        finally:
            if con:
                con.close()


# ============================================================
#  TERMINOLOGIAS  (ConceptMap del RF3)
# ============================================================

def mapear_terminologia(sistema, codigo_local):
    """
    Traduce el codigo propio de la sede al estandar internacional.
        mapear('CIE10', 'DM2')               -> 'E11'
        mapear('LOINC', 'GLUCOSA EN SANGRE') -> '2339-0'

    Devuelve None si no hay mapeo. Se prefiere guardar el recurso
    sin codigo estandar antes que perder el dato clinico.
    """
    if codigo_local is None or len(str(codigo_local).strip()) == 0:
        return None
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor()
        cur.execute("SELECT codigo_std FROM ref_terminologia "
                    "WHERE sistema = %s AND upper(codigo_local) = upper(%s)",
                    (sistema, str(codigo_local).strip()))
        fila = cur.fetchone()
        cur.close()
        return fila[0] if fila else None
    except Exception as e:
        print("ERROR mapeando terminologia:", e)
        return None
    finally:
        if con:
            con.close()


# ============================================================
#  ENTREGA A HAPI FHIR
# ============================================================

def enviar_bundle_a_hapi(bundle_json):
    """
    Hace el POST del Bundle a HAPI.

    Devuelve (exito, detalle). Se usa urllib del propio Python en
    vez de una libreria HTTP extra: una peticion POST con una
    cabecera no justifica una dependencia mas.
    """
    datos = bundle_json.encode("utf-8")
    peticion = urllib.request.Request(
        HAPI_URL,
        data=datos,
        headers={"Content-Type": "application/fhir+json"},
        method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=20) as r:
            cuerpo = r.read().decode("utf-8", "replace")
            if 200 <= r.status < 300:
                # Se devuelve el cuerpo ENTERO, no recortado: de el
                # se saca el id real del Patient que creo HAPI.
                return True, cuerpo
            return False, "HTTP %d: %s" % (r.status, cuerpo[:300])
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        return False, "HTTP %d: %s" % (e.code, cuerpo[:300])
    except Exception as e:
        # Aqui cae el caso de HAPI apagado: se reintentara
        return False, "No se pudo conectar con HAPI: " + str(e)


def extraer_patient_id(respuesta_hapi):
    """
    Saca el id del Patient de la respuesta de una transaccion FHIR.

    HAPI contesta un Bundle de tipo transaction-response con una
    entrada por cada recurso enviado, y en cada una un campo
    response.location con esta forma:

        "Patient/5/_history/1"
         \_____/ \_/
          tipo    id

    Se recorren las entradas buscando la que empieza por
    "Patient/", en vez de dar por hecho que es la primera: el
    orden del Bundle podria cambiar el dia que se anada otro
    recurso al principio, y entonces se estaria guardando como id
    de paciente el de un Encounter.

    Devuelve el id o None si no viene.
    """
    try:
        datos = json.loads(respuesta_hapi)
    except Exception:
        return None

    for entrada in datos.get("entry", []):
        lugar = entrada.get("response", {}).get("location", "")
        if lugar.startswith("Patient/"):
            partes = lugar.split("/")
            if len(partes) >= 2 and partes[1] != "":
                return partes[1]
    return None


def marcar_cobertura_fhir(documento_id, fhir_id):
    """
    Escribe fhir_patient_id en el nodo del paciente.

    Esto alimenta el TABLERO DE COBERTURA del RF6: la cobertura de
    una sede es el porcentaje de pacientes con este campo lleno.
    Empieza en 0% y sube a 100% segun entran los mensajes.
    """
    con = None
    try:
        con, nombre_nodo = conectar_nodo(documento_id)
        cur = con.cursor()
        cur.execute("UPDATE usuario SET fhir_patient_id = %s, updated_at = now() "
                    "WHERE documento_id = %s", (fhir_id, int(documento_id)))
        con.commit()
        cur.close()
        return True
    except Exception as e:
        print("ERROR marcando cobertura:", e)
        return False
    finally:
        if con:
            con.close()


# ============================================================
#  LA CADENA DE PROCESAMIENTO
# ============================================================

def construir_bundle_desde_mensaje(m):
    """
    Transforma un MensajeClinico ya validado en un Bundle FHIR.
    Aqui es donde se aplican las terminologias.
    """
    fecha_nac = normalizador.normalizar_fecha(m.fecha_nac_cruda)
    genero = normalizador.normalizar_genero(m.sexo_crudo)
    fecha_atencion = normalizador.normalizar_fecha_hora(m.fecha_atencion_cruda)
    clase = normalizador.normalizar_clase_encuentro(m.tipo_atencion)

    entradas = []

    # 1. Patient - con ifNoneExist, porque el MISMO paciente llega
    #    desde las tres sedes y no debe duplicarse.
    entradas.append({
        "recurso": normalizador.construir_patient(
            m.documento, m.nombres, m.apellidos, fecha_nac, genero, m.sede),
        "tipo": "Patient",
        "si_no_existe": "identifier=%s|%s" % (
            normalizador.SISTEMA_DOCUMENTO, m.documento),
    })

    # 2. Encounter - cada atencion es un evento real distinto,
    #    asi que NO lleva ifNoneExist.
    #
    # Si la sede MANDO una fecha pero no se pudo interpretar, el
    # mensaje se rechaza en vez de seguir sin el Encounter. Antes
    # la atencion desaparecia en silencio: llegaban el paciente y
    # el diagnostico, pero la visita no, y nadie veia el fallo.
    # Perder datos sin avisar es peor que rechazar el mensaje.
    if m.fecha_atencion_cruda is not None \
            and str(m.fecha_atencion_cruda).strip() != "" \
            and fecha_atencion is None:
        raise ValueError(
            "No se pudo interpretar la fecha de atencion '%s'"
            % m.fecha_atencion_cruda)

    if fecha_atencion is not None:
        entradas.append({
            "recurso": normalizador.construir_encounter(
                m.documento, fecha_atencion, clase, m.triage, m.sede),
            "tipo": "Encounter",
        })

    # 3. Condition - el codigo local se traduce a CIE-10
    if m.dx_codigo_local:
        cie10 = mapear_terminologia("CIE10", m.dx_codigo_local)
        if cie10 is None:
            cie10 = m.dx_codigo_local      # sin mapeo: se conserva el local
        entradas.append({
            "recurso": normalizador.construir_condition(
                m.documento, cie10, m.dx_descripcion, fecha_atencion, m.sede),
            "tipo": "Condition",
        })

    # 4. Observation - la prueba local se traduce a LOINC
    if m.lab_prueba_local and m.lab_valor:
        loinc = mapear_terminologia("LOINC", m.lab_prueba_local)
        if loinc is None:
            loinc = "unknown"
        entradas.append({
            "recurso": normalizador.construir_observation(
                m.documento, loinc, m.lab_prueba_local,
                m.lab_valor, m.lab_unidad, fecha_atencion, m.sede),
            "tipo": "Observation",
        })

    return normalizador.construir_bundle(entradas)


def actualizar_estado(hash_mensaje, estado, intentos=None,
                      error=None, entregado=False, documento_id=None):
    """Mueve el mensaje por los estados del diagrama de estados."""
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor()
        partes = ["estado = %s", "actualizado_en = now()"]
        valores = [estado]

        if intentos is not None:
            partes.append("intentos = %s")
            valores.append(intentos)
        if error is not None:
            partes.append("error_detalle = %s")
            valores.append(error[:2000])
        if documento_id is not None:
            partes.append("documento_id = %s")
            valores.append(int(documento_id))
        if entregado:
            partes.append("entregado_en = now()")

        valores.append(hash_mensaje)
        cur.execute("UPDATE mensaje_bus SET " + ", ".join(partes) +
                    " WHERE hash_mensaje = %s", valores)
        con.commit()
        cur.close()
    except Exception as e:
        print("ERROR actualizando estado:", e)
    finally:
        if con:
            con.close()


def programar_reintento(hash_mensaje, intentos, error):
    """
    Agenda el proximo intento con RETROCESO EXPONENCIAL.

        intento 1 -> espera  2s
        intento 2 -> espera  4s
        intento 3 -> espera  8s
        intento 4 -> espera 16s
        intento 5 -> espera 32s

    Esperar cada vez mas evita martillar un servicio que ya esta
    caido y le da tiempo real a recuperarse. Si se agotan los
    intentos, el mensaje pasa a MUERTO (la DLQ).
    """
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor()

        if intentos >= MAX_INTENTOS:
            cur.execute(
                "UPDATE mensaje_bus SET estado='MUERTO', intentos=%s, "
                "error_detalle=%s, actualizado_en=now() "
                "WHERE hash_mensaje=%s",
                (intentos, "Agotados %d intentos. Ultimo error: %s"
                 % (intentos, str(error)[:1500]), hash_mensaje))
            print("  -> MUERTO (DLQ) tras %d intentos" % intentos)
        else:
            espera = ESPERA_BASE ** intentos
            cur.execute(
                "UPDATE mensaje_bus SET estado='FALLIDO', intentos=%s, "
                "error_detalle=%s, proximo_intento = now() + (%s || ' seconds')::interval, "
                "actualizado_en=now() WHERE hash_mensaje=%s",
                (intentos, str(error)[:2000], str(espera), hash_mensaje))
            print("  -> FALLIDO, reintento %d en %ds" % (intentos + 1, espera))

        con.commit()
        cur.close()
    except Exception as e:
        print("ERROR programando reintento:", e)
    finally:
        if con:
            con.close()


def procesar(m, hash_mensaje, intento_numero=0):
    """
    Ejecuta la cadena completa sobre un mensaje ya reservado.
    Devuelve un diccionario con el resultado.
    """
    # ---- VALIDACION ----
    if not m.es_valido():
        actualizar_estado(hash_mensaje, "RECHAZADO", intentos=intento_numero,
                          error=m.error_validacion)
        registrar_auditoria("hsb", "sistema", "INGESTAR", "Mensaje",
                            m.documento, "RECHAZADO", m.error_validacion)
        print("  -> RECHAZADO:", m.error_validacion)
        return {"estado": "RECHAZADO", "motivo": m.error_validacion}

    actualizar_estado(hash_mensaje, "VALIDADO", documento_id=m.documento)

    # ---- TRANSFORMACION ----
    try:
        bundle = construir_bundle_desde_mensaje(m)
    except Exception as e:
        actualizar_estado(hash_mensaje, "RECHAZADO", intentos=intento_numero,
                          error="Error transformando a FHIR: " + str(e))
        return {"estado": "RECHAZADO", "motivo": "Error de transformacion: " + str(e)}

    actualizar_estado(hash_mensaje, "TRANSFORMADO")

    # ---- ENTREGA ----
    ok, detalle = enviar_bundle_a_hapi(bundle)
    if not ok:
        programar_reintento(hash_mensaje, intento_numero + 1, detalle)
        return {"estado": "FALLIDO", "motivo": detalle,
                "intentos": intento_numero + 1}

    # ---- COBERTURA FHIR + AUDITORIA ----
    # Se guarda el id REAL que devolvio HAPI, no un marcador: asi
    # la cobertura del tablero se puede comprobar una por una
    # contra el servidor FHIR. Si HAPI no lo devolviera, se deja
    # el hash del mensaje como rastro para poder investigarlo, y
    # no un valor inventado que parezca un id valido.
    patient_id = extraer_patient_id(detalle)
    if patient_id is None:
        patient_id = "sin-id-" + hash_mensaje[:12]
    marcar_cobertura_fhir(m.documento, patient_id)
    actualizar_estado(hash_mensaje, "ENTREGADO", intentos=intento_numero,
                      entregado=True, documento_id=m.documento)
    registrar_auditoria("hsb", "sistema", "INGESTAR", "Bundle",
                        m.documento, "PERMITIDO",
                        "%s desde %s" % (m.formato, m.sede))
    print("  -> ENTREGADO")
    return {"estado": "ENTREGADO", "documento": m.documento, "sede": m.sede}


def recibir(contenido, formato, sede):
    """
    Punto de entrada unico del bus. Hace la reserva de idempotencia
    y lanza la cadena.
    """
    hash_mensaje = calcular_hash(contenido)

    # ---- IDEMPOTENCIA ----
    # El INSERT con ON CONFLICT DO NOTHING es atomico: si el hash ya
    # existe no inserta y devuelve 0 filas. No hay ventana de carrera.
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO mensaje_bus (hash_mensaje, sede, formato, estado, "
            "                         contenido, max_intentos) "
            "VALUES (%s,%s,%s,'RECIBIDO',%s,%s) "
            "ON CONFLICT (hash_mensaje) DO NOTHING",
            (hash_mensaje, sede, formato, contenido, MAX_INTENTOS))
        nuevo = (cur.rowcount == 1)
        con.commit()
        cur.close()
    except Exception as e:
        return {"estado": "ERROR", "motivo": "No se pudo registrar: " + str(e)}
    finally:
        if con:
            con.close()

    if not nuevo:
        print("  -> DUPLICADO, se descarta (hash %s)" % hash_mensaje[:12])
        return {"estado": "DUPLICADO", "hash": hash_mensaje,
                "motivo": "Este mensaje ya fue procesado antes"}

    # ---- PARSEO segun el formato ----
    if formato == "HL7":
        m = parsers.parsear_hl7(contenido, sede)
    elif formato == "CSV":
        m = parsers.parsear_csv(contenido, sede)
    else:
        m = parsers.parsear_json(contenido, sede)

    print("RECIBIDO", m.resumen())
    resultado = procesar(m, hash_mensaje, 0)
    resultado["hash"] = hash_mensaje
    return resultado


# ============================================================
#  TRABAJADOR DE REINTENTOS  (hilo en segundo plano)
# ============================================================

def trabajador_reintentos():
    """
    Cada 5 segundos busca mensajes FALLIDOS cuyo momento de
    reintento ya paso, y los vuelve a procesar.

    Corre en un hilo aparte para que no bloquee la recepcion de
    mensajes nuevos: el bus sigue atendiendo mientras reintenta.
    """
    print("[reintentos] trabajador iniciado")
    while True:
        time.sleep(5)
        con = None
        try:
            con = conectar_bus()
            cur = con.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT hash_mensaje, sede, formato, contenido, intentos "
                "FROM mensaje_bus "
                "WHERE estado = 'FALLIDO' AND proximo_intento <= now() "
                "ORDER BY proximo_intento LIMIT 10")
            pendientes = cur.fetchall()
            cur.close()
            con.close()
            con = None

            for p in pendientes:
                print("[reintentos] intento %d de %s"
                      % (p["intentos"] + 1, p["hash_mensaje"][:12]))
                actualizar_estado(p["hash_mensaje"], "REINTENTANDO")

                if p["formato"] == "HL7":
                    m = parsers.parsear_hl7(p["contenido"], p["sede"])
                elif p["formato"] == "CSV":
                    m = parsers.parsear_csv(p["contenido"], p["sede"])
                else:
                    m = parsers.parsear_json(p["contenido"], p["sede"])

                procesar(m, p["hash_mensaje"], p["intentos"])

        except Exception as e:
            print("[reintentos] error:", e)
        finally:
            if con:
                con.close()


@app.on_event("startup")
def al_arrancar():
    # daemon=True hace que el hilo muera con el proceso principal,
    # para que el contenedor pueda pararse limpio.
    h = threading.Thread(target=trabajador_reintentos, daemon=True)
    h.start()


# ============================================================
#  ENDPOINTS DE INGESTA  (RF1)
# ============================================================

def autorizar_ingesta(request):
    """
    Portero de la ingesta. Devuelve (quien, None) o (None, error).

    ADMITE DOS CREDENCIALES, porque hay dos clases de cliente:

      1. CLAVE DE SERVICIO en la cabecera X-Sede-Clave.
         Es la que usa Mirth y la que usarian los sistemas de las
         sedes. Un proceso automatico no puede escribir una clave
         en un formulario cada hora, asi que no le sirve un token
         que caduca. Es una API key.

      2. TOKEN JWT con el permiso INGESTAR.
         Para pruebas manuales y para cualquier cliente que ya
         tenga sesion abierta.

    Lo que NO se admite es entrar sin credencial. Antes de esto,
    cualquiera que alcanzara el puerto 8002 podia inyectar
    historias clinicas en el sistema.
    """
    clave = request.headers.get("x-sede-clave")
    if clave is not None and seguridad.hmac.compare_digest(clave, CLAVE_SEDE):
        return ("sistema-sede", None)

    token = seguridad.extraer_token_de_cabecera(
        request.headers.get("authorization"))
    valido, datos = seguridad.verificar_token(token)
    if valido and seguridad.puede(datos.get("rol"), "INGESTAR"):
        return (datos.get("usuario"), None)

    motivo = datos if not valido else "el rol no tiene el permiso INGESTAR"
    registrar_auditoria("anonimo", "?", "INGESTAR", "Mensaje", None,
                        "DENEGADO", str(motivo))
    return (None, JSONResponse(
        {"error": "no autenticado",
         "motivo": "la ingesta exige la cabecera X-Sede-Clave "
                   "o un token con permiso INGESTAR"},
        status_code=401))


@app.post("/ingesta/hl7")
async def ingesta_hl7(request: Request, sede: str = "sede1"):
    """
    Recibe un mensaje HL7 v2 en texto plano.
    Lo usa Mirth Connect: recibe el MLLP, responde el ACK y
    reenvia aqui el mensaje crudo.
    """
    quien, error = autorizar_ingesta(request)
    if error is not None:
        return error

    cuerpo = (await request.body()).decode("utf-8", "replace")
    return recibir(cuerpo, "HL7", SEDES.get(sede, sede))


@app.post("/ingesta/csv")
async def ingesta_csv(request: Request, sede: str = "sede2"):
    """Recibe UNA linea de CSV legado."""
    quien, error = autorizar_ingesta(request)
    if error is not None:
        return error

    cuerpo = (await request.body()).decode("utf-8", "replace")
    return recibir(cuerpo.strip(), "CSV", SEDES.get(sede, sede))


@app.post("/ingesta/json")
async def ingesta_json(request: Request, sede: str = "sede3"):
    """Recibe un objeto JSON legado."""
    quien, error = autorizar_ingesta(request)
    if error is not None:
        return error

    cuerpo = (await request.body()).decode("utf-8", "replace")
    return recibir(cuerpo.strip(), "JSON", SEDES.get(sede, sede))


# ============================================================
#  OBSERVABILIDAD  (RNF: /health y /metrics en cada servicio)
# ============================================================

@app.get("/health")
def health():
    """
    Estado del bus y de sus dependencias.

    Devuelve 'degradado' y no 'caido' si falla una dependencia:
    el bus puede seguir recibiendo y encolando aunque HAPI este
    abajo. Eso ES la tolerancia a fallos parciales.
    """
    estado = {"servicio": "hsb", "estado": "ok", "dependencias": {}}

    # Si nadie configuro el secreto real, que se vea en voz alta.
    if seguridad.usando_secreto_de_desarrollo():
        estado["aviso_seguridad"] = ("JWT_SECRETO no configurado: se esta "
                                     "usando el secreto de desarrollo")

    try:
        con = conectar_bus()
        con.close()
        estado["dependencias"]["bus_db"] = "ok"
    except Exception as e:
        estado["dependencias"]["bus_db"] = "caido: " + str(e)[:100]
        estado["estado"] = "degradado"

    try:
        with urllib.request.urlopen(HAPI_URL + "/metadata", timeout=5) as r:
            estado["dependencias"]["hapi"] = "ok" if r.status == 200 else str(r.status)
    except Exception as e:
        estado["dependencias"]["hapi"] = "caido: " + str(e)[:100]
        estado["estado"] = "degradado"

    for n in NODOS:
        try:
            c = psycopg2.connect(host=n["host"], port=n["port"], user=NODO_USER,
                                 password=NODO_PASS, dbname=NODO_DB,
                                 connect_timeout=3)
            c.close()
            estado["dependencias"][n["nombre"]] = "ok"
        except Exception:
            estado["dependencias"][n["nombre"]] = "caido"
            estado["estado"] = "degradado"

    codigo = 200 if estado["estado"] == "ok" else 503
    return JSONResponse(content=estado, status_code=codigo)


@app.get("/metrics")
def metrics():
    """
    Metricas del bus en formato de texto (estilo Prometheus).
    El enunciado pide medir "mensajes por minuto, latencia media
    de extremo a extremo y porcentaje de fallidos".
    """
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM v_metricas_bus")
        m = cur.fetchone()

        cur.execute("SELECT count(*) AS n FROM mensaje_bus "
                    "WHERE recibido_en > now() - interval '1 minute'")
        por_minuto = cur.fetchone()["n"]
        cur.close()

        lineas = [
            "# HELP hsb_mensajes_total Mensajes recibidos por el bus",
            "hsb_mensajes_total %s" % m["total"],
            "hsb_mensajes_entregados %s" % m["entregados"],
            "hsb_mensajes_rechazados %s" % m["rechazados"],
            "hsb_mensajes_muertos %s" % m["muertos"],
            "hsb_mensajes_en_reintento %s" % m["en_reintento"],
            "hsb_mensajes_con_reintentos %s" % m["con_reintentos"],
            "# HELP hsb_latencia_media_ms Latencia media de extremo a extremo",
            "hsb_latencia_media_ms %s" % m["latencia_media_ms"],
            "# HELP hsb_porcentaje_fallidos Porcentaje de mensajes fallidos",
            "hsb_porcentaje_fallidos %s" % m["porcentaje_fallidos"],
            "# HELP hsb_mensajes_por_minuto Mensajes del ultimo minuto",
            "hsb_mensajes_por_minuto %s" % por_minuto,
        ]
        return PlainTextResponse("\n".join(lineas) + "\n")
    except Exception as e:
        return PlainTextResponse("# error leyendo metricas: %s\n" % e,
                                 status_code=503)
    finally:
        if con:
            con.close()


@app.get("/cola")
def ver_cola():
    """Estado de la cola: util para la demo y para depurar."""
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT hash_mensaje, sede, formato, estado, intentos, "
            "       documento_id, error_detalle, recibido_en, entregado_en "
            "FROM mensaje_bus ORDER BY id DESC LIMIT 50")
        filas = cur.fetchall()
        cur.close()
        for f in filas:
            f["hash_mensaje"] = f["hash_mensaje"][:12]
            f["recibido_en"] = str(f["recibido_en"])
            f["entregado_en"] = str(f["entregado_en"]) if f["entregado_en"] else None
        return {"mensajes": filas}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    finally:
        if con:
            con.close()


@app.get("/dlq")
def ver_dlq():
    """
    Lo que no se entrego, separado en dos listas.

    MUERTO y RECHAZADO no son lo mismo y por eso van aparte:

      MUERTO     el mensaje estaba bien, pero su destino fallo.
                 Se reintento hasta agotar el limite. Tiene
                 sentido reprocesarlo cuando el destino vuelva.

      RECHAZADO  el mensaje esta mal formado. Reintentarlo daria
                 exactamente el mismo error, asi que no se
                 reintenta: hay que corregirlo en la sede.

    Devolverlos en una sola lista haria creer que se arreglan
    igual, y no es asi.
    """
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT hash_mensaje, sede, formato, estado, intentos, "
            "       error_detalle, recibido_en FROM mensaje_bus "
            "WHERE estado IN ('MUERTO','RECHAZADO') ORDER BY id DESC LIMIT 50")
        filas = cur.fetchall()
        cur.close()
        muertos = []
        rechazados = []
        for f in filas:
            f["hash_mensaje"] = f["hash_mensaje"][:12]
            f["recibido_en"] = str(f["recibido_en"])
            if f["estado"] == "MUERTO":
                muertos.append(f)
            else:
                rechazados.append(f)
        return {
            "mensajes_muertos": muertos,
            "mensajes_rechazados": rechazados,
            "nota": ("MUERTO: el destino fallo y se agotaron los reintentos; "
                     "se puede reprocesar. RECHAZADO: el mensaje esta mal "
                     "formado; hay que corregirlo en la sede."),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    finally:
        if con:
            con.close()


@app.post("/reprocesar/{hash_parcial}")
def reprocesar(hash_parcial: str):
    """
    Devuelve a la cola un mensaje que quedo en la DLQ.

    La DLQ no es una papelera: es una bandeja de revision. Cuando
    el operador arregla la causa (levantar el servicio caido,
    corregir una ruta), reencola el mensaje desde aqui en vez de
    pedirle a la sede que lo reenvie.

    El contenido original se guardo en mensaje_bus.contenido, asi
    que se puede reprocesar sin volver a molestar al origen.
    """
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT hash_mensaje, sede, formato, contenido FROM mensaje_bus "
            "WHERE hash_mensaje LIKE %s AND estado IN ('MUERTO','RECHAZADO') "
            "LIMIT 1", (hash_parcial + "%",))
        fila = cur.fetchone()
        cur.close()
        con.close()
        con = None

        if fila is None:
            return JSONResponse(
                {"error": "No hay mensaje muerto con ese hash"}, status_code=404)

        # Se reinicia el contador: es un reproceso deliberado,
        # no la continuacion de los intentos automaticos.
        actualizar_estado(fila["hash_mensaje"], "REINTENTANDO", intentos=0,
                          error="Reprocesado manualmente")

        if fila["formato"] == "HL7":
            m = parsers.parsear_hl7(fila["contenido"], fila["sede"])
        elif fila["formato"] == "CSV":
            m = parsers.parsear_csv(fila["contenido"], fila["sede"])
        else:
            m = parsers.parsear_json(fila["contenido"], fila["sede"])

        resultado = procesar(m, fila["hash_mensaje"], 0)
        resultado["reprocesado"] = True
        return resultado

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if con:
            con.close()


# ============================================================
#  AUTENTICACION Y AUTORIZACION  (RF5)
#
#  El bus es el servidor de identidad del sistema: es el que
#  tiene bus_db, donde viven los usuarios y la bitacora. Emite
#  el token; los demas servicios lo VALIDAN solos con el secreto
#  compartido, sin preguntarle nada a nadie (ver seguridad.py).
# ============================================================

def buscar_usuario(usuario):
    """Lee un usuario de bus_db. Devuelve el diccionario o None."""
    con = None
    try:
        con = conectar_bus()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT usuario, rol, sal, clave_hash, documento_id, activo "
            "FROM usuario_sistema WHERE usuario = %s", (usuario,))
        fila = cur.fetchone()
        cur.close()
        return fila
    except Exception as e:
        print("ERROR buscando usuario:", e)
        return None
    finally:
        if con:
            con.close()


@app.post("/auth/login")
async def login(request: Request):
    """
    Recibe {"usuario": "...", "clave": "..."} y devuelve el token.

    EL MENSAJE DE ERROR ES EL MISMO SIEMPRE ("usuario o clave
    incorrectos"), tanto si el usuario no existe como si la clave
    esta mal. Si dijeramos "ese usuario no existe", un atacante
    podria averiguar que usuarios son validos probando nombres
    (enumeracion de usuarios).
    """
    try:
        cuerpo = await request.json()
    except Exception:
        return JSONResponse({"error": "se esperaba JSON"}, status_code=400)

    usuario = str(cuerpo.get("usuario", "")).strip()
    clave = str(cuerpo.get("clave", ""))

    if usuario == "" or clave == "":
        return JSONResponse({"error": "faltan usuario o clave"},
                            status_code=400)

    fila = buscar_usuario(usuario)

    # Comprobaciones separadas, pero TODAS con la misma respuesta
    if fila is None:
        registrar_auditoria(usuario, "?", "LOGIN", "Sesion", None,
                            "DENEGADO", "usuario inexistente")
        return JSONResponse({"error": "usuario o clave incorrectos"},
                            status_code=401)

    if not fila["activo"]:
        registrar_auditoria(usuario, fila["rol"], "LOGIN", "Sesion", None,
                            "DENEGADO", "usuario inactivo")
        return JSONResponse({"error": "usuario o clave incorrectos"},
                            status_code=401)

    if not seguridad.clave_correcta(clave, fila["sal"], fila["clave_hash"]):
        registrar_auditoria(usuario, fila["rol"], "LOGIN", "Sesion", None,
                            "DENEGADO", "clave incorrecta")
        return JSONResponse({"error": "usuario o clave incorrectos"},
                            status_code=401)

    token = seguridad.crear_token(fila["usuario"], fila["rol"],
                                  fila["documento_id"])

    registrar_auditoria(usuario, fila["rol"], "LOGIN", "Sesion",
                        fila["documento_id"], "PERMITIDO", "token emitido")

    return {
        "token": token,
        "usuario": fila["usuario"],
        "rol": fila["rol"],
        "documento_id": fila["documento_id"],
        "permisos": seguridad.PERMISOS.get(fila["rol"], []),
        "vigencia_minutos": seguridad.VIGENCIA_MINUTOS,
    }


def autorizar(request, accion, documento_pedido=None):
    """
    Portero de los endpoints protegidos.

    Devuelve (datos_del_token, None) si deja pasar, o
    (None, respuesta_de_error) si no.

    Se usa asi, sin magia:

        datos, error = autorizar(request, "VER_AUDITORIA")
        if error is not None:
            return error

    LOS TRES CONTROLES, EN ESTE ORDEN:
      1. Autenticacion: el token existe, esta firmado y vigente.
      2. Autorizacion por rol: ese rol tiene ese permiso.
      3. Autorizacion por PERTENENCIA: un paciente con permiso
         para ver "su" historia no puede ver la de otro. El rol
         solo no basta; hay que comparar el documento del token
         con el documento que esta pidiendo.

    TODO INTENTO DENEGADO QUEDA EN LA BITACORA. El enunciado pide
    "evidencia de accesos permitidos y denegados": los denegados
    son justamente los que hay que poder demostrar despues.
    """
    token = seguridad.extraer_token_de_cabecera(
        request.headers.get("authorization"))

    valido, resultado = seguridad.verificar_token(token)
    if not valido:
        registrar_auditoria("anonimo", "?", accion, "Autenticacion",
                            documento_pedido, "DENEGADO", str(resultado))
        return (None, JSONResponse({"error": "no autenticado",
                                    "motivo": resultado}, status_code=401))

    datos = resultado
    usuario = datos.get("usuario")
    rol = datos.get("rol")

    if not seguridad.puede(rol, accion):
        registrar_auditoria(usuario, rol, accion, "Autorizacion",
                            documento_pedido, "DENEGADO",
                            "el rol %s no tiene el permiso %s" % (rol, accion))
        return (None, JSONResponse(
            {"error": "no autorizado",
             "motivo": "el rol %s no puede %s" % (rol, accion)},
            status_code=403))

    if rol == "paciente" and documento_pedido is not None:
        suyo = datos.get("documento_id")
        if suyo is None or int(documento_pedido) != int(suyo):
            registrar_auditoria(usuario, rol, accion, "HistoriaClinica",
                                documento_pedido, "DENEGADO",
                                "intento de ver la historia de otra persona")
            return (None, JSONResponse(
                {"error": "no autorizado",
                 "motivo": "solo puede consultar su propia historia"},
                status_code=403))

    return (datos, None)


@app.get("/auth/yo")
def quien_soy(request: Request):
    """Devuelve lo que dice el token. Lo usa el front para pintar el menu."""
    token = seguridad.extraer_token_de_cabecera(
        request.headers.get("authorization"))
    valido, resultado = seguridad.verificar_token(token)
    if not valido:
        return JSONResponse({"error": "no autenticado", "motivo": resultado},
                            status_code=401)
    return {
        "usuario": resultado.get("usuario"),
        "rol": resultado.get("rol"),
        "documento_id": resultado.get("documento_id"),
        "permisos": seguridad.PERMISOS.get(resultado.get("rol"), []),
        "caduca_en": resultado.get("exp"),
    }


# ============================================================
#  BITACORA DE AUDITORIA  (RF5)
# ============================================================

@app.post("/auditoria/evento")
async def anotar_evento(request: Request):
    """
    Un servicio pide que se anote un evento en la bitacora.

    POR QUE LA APP NO ESCRIBE DIRECTO EN LA TABLA:
    la cadena de hash exige que haya UN SOLO escritor. Dentro de
    un proceso basta un Lock, pero la app y el bus son procesos
    distintos en contenedores distintos: dos Locks separados no
    se ven entre ellos, leerian el mismo hash_anterior y la
    cadena se bifurcaria. Centralizando la escritura en el bus
    hay un unico punto de serializacion y la cadena no se puede
    romper por una carrera.
    """
    try:
        cuerpo = await request.json()
    except Exception:
        return JSONResponse({"error": "se esperaba JSON"}, status_code=400)

    # DOS MANERAS DE IDENTIFICARSE, y cambian de donde sale el
    # nombre que queda escrito en la bitacora:
    #
    #  1. CON TOKEN DE USUARIO: el usuario y el rol se toman DEL
    #     TOKEN, nunca del cuerpo. Si se tomaran del cuerpo,
    #     cualquiera podria firmar la bitacora con el nombre de
    #     otro.
    #
    #  2. CON LA CLAVE DE SERVICIO: la usa la app, que es un
    #     servicio de confianza dentro de la red interna. Ahi si
    #     se acepta el usuario que venga en el cuerpo, porque la
    #     app esta anotando POR CUENTA de alguien: necesita poder
    #     registrar tambien los intentos de quien NO tiene token
    #     valido, que son justamente los que hay que auditar.
    #     Si se exigiera token, un acceso anonimo denegado no
    #     dejaria rastro, que es el caso mas importante.
    clave = request.headers.get("x-sede-clave")
    if clave is not None and seguridad.hmac.compare_digest(clave, CLAVE_SEDE):
        usuario_evento = str(cuerpo.get("usuario_sistema", "servicio"))
        rol_evento = str(cuerpo.get("rol_sistema", "?"))
    else:
        token = seguridad.extraer_token_de_cabecera(
            request.headers.get("authorization"))
        valido, datos = seguridad.verificar_token(token)
        if not valido:
            return JSONResponse({"error": "no autenticado", "motivo": datos},
                                status_code=401)
        usuario_evento = datos.get("usuario")
        rol_evento = datos.get("rol")

    h = registrar_auditoria(
        usuario_evento, rol_evento,
        str(cuerpo.get("accion", "DESCONOCIDA")),
        str(cuerpo.get("recurso", "")),
        cuerpo.get("documento_id"),
        str(cuerpo.get("resultado", "PERMITIDO")),
        str(cuerpo.get("detalle", "")))

    if h is None:
        return JSONResponse({"error": "no se pudo anotar"}, status_code=503)
    return {"anotado": True, "hash": h}


@app.get("/auditoria")
def ver_auditoria(request: Request, limite: int = 100):
    """La bitacora. Solo el auditor."""
    datos, error = autorizar(request, "VER_AUDITORIA")
    if error is not None:
        return error

    con = None
    try:
        con = conectar_bus()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT secuencia, ts, usuario, rol, accion, recurso, "
            "       documento_id, resultado, detalle, hash_actual "
            "FROM evento_auditoria ORDER BY secuencia DESC LIMIT %s",
            (limite,))
        filas = cur.fetchall()
        cur.close()
        for f in filas:
            f["ts"] = str(f["ts"])
            f["hash_actual"] = f["hash_actual"][:12]
        return {"eventos": filas, "consultado_por": datos.get("usuario")}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    finally:
        if con:
            con.close()


def recalcular_hash_evento(fila, hash_anterior):
    """
    Repite el calculo que hizo registrar_auditoria.

    Tiene que ser EXACTAMENTE el mismo, con el mismo separador y
    el mismo orden de campos, o la verificacion daria falsas
    alarmas. Por eso el ts se vuelve a formatear con isoformat():
    es lo que se guardo.
    """
    contenido = "|".join([
        fila["ts"].isoformat(),
        str(fila["usuario"]), str(fila["rol"]), str(fila["accion"]),
        str(fila["recurso"]), str(fila["documento_id"]),
        str(fila["resultado"]), str(fila["detalle"]),
    ])
    return hashlib.sha256(
        (contenido + hash_anterior).encode("utf-8")).hexdigest()


@app.get("/auditoria/verificar")
def verificar_auditoria(request: Request):
    """
    Recorre la bitacora entera y comprueba la cadena de hash.

    DOS COMPROBACIONES POR CADA FILA:

      a) INTEGRIDAD DEL CONTENIDO
         Se recalcula SHA-256(contenido + hash_anterior) y se
         compara con el hash_actual guardado. Si alguien edito
         un campo (el usuario, el resultado, el documento), el
         hash recalculado ya no coincide.

      b) CONTINUIDAD DE LA CADENA
         El hash_anterior de esta fila tiene que ser igual al
         hash_actual de la fila de antes. Si alguien BORRO una
         fila del medio, los contenidos siguen cuadrando uno a
         uno pero el eslabon se rompe justo ahi.

    Hacen falta las dos: la primera detecta modificaciones, la
    segunda detecta borrados y reordenamientos.
    """
    datos, error = autorizar(request, "VERIFICAR_AUDITORIA")
    if error is not None:
        return error

    con = None
    try:
        con = conectar_bus()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT secuencia, ts, usuario, rol, accion, recurso, "
            "       documento_id, resultado, detalle, "
            "       hash_anterior, hash_actual "
            "FROM evento_auditoria ORDER BY secuencia ASC")
        filas = cur.fetchall()
        cur.close()

        problemas = []
        hash_esperado_anterior = "GENESIS"
        revisados = 0

        for fila in filas:
            revisados = revisados + 1

            # (b) continuidad
            if fila["hash_anterior"] != hash_esperado_anterior:
                problemas.append({
                    "secuencia": fila["secuencia"],
                    "tipo": "CADENA_ROTA",
                    "explicacion": "el hash_anterior de esta fila no es el "
                                   "hash_actual de la fila previa: falta una "
                                   "fila o se reordenaron",
                    "esperaba": hash_esperado_anterior[:16],
                    "encontro": str(fila["hash_anterior"])[:16],
                })

            # (a) integridad del contenido
            recalculado = recalcular_hash_evento(fila, fila["hash_anterior"])
            if recalculado != fila["hash_actual"]:
                problemas.append({
                    "secuencia": fila["secuencia"],
                    "tipo": "CONTENIDO_ALTERADO",
                    "explicacion": "el contenido de esta fila fue modificado "
                                   "despues de escribirse",
                    "hash_guardado": fila["hash_actual"][:16],
                    "hash_recalculado": recalculado[:16],
                    "fila": {
                        "usuario": fila["usuario"], "rol": fila["rol"],
                        "accion": fila["accion"], "recurso": fila["recurso"],
                        "documento_id": fila["documento_id"],
                        "resultado": fila["resultado"],
                    },
                })

            # Para la fila siguiente se usa lo que ESTA guardado,
            # no lo recalculado: asi un solo cambio no hace que
            # todas las filas posteriores salgan rotas y se puede
            # senalar el punto exacto de la manipulacion.
            hash_esperado_anterior = fila["hash_actual"]

        registrar_auditoria(datos.get("usuario"), datos.get("rol"),
                            "VERIFICAR_AUDITORIA", "Bitacora", None,
                            "PERMITIDO",
                            "%d eventos revisados, %d problemas"
                            % (revisados, len(problemas)))

        return {
            "integra": len(problemas) == 0,
            "eventos_revisados": revisados,
            "problemas_encontrados": len(problemas),
            "problemas": problemas,
            "veredicto": ("La bitacora esta intacta"
                          if len(problemas) == 0 else
                          "SE DETECTO MANIPULACION en la bitacora"),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    finally:
        if con:
            con.close()
