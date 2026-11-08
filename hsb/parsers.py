"""
============================================================
 PARSERS DE LOS FORMATOS LEGADOS  (RF1)
============================================================

Entran tres formatos distintos y sale uno solo:

    HL7 v2 ---\\
    CSV    -----> MensajeClinico ---> normalizador ---> FHIR
    JSON   ---/

MensajeClinico es el MODELO CANONICO intermedio. Existe para que
la transformacion a FHIR se escriba UNA sola vez. Si cada parser
produjera FHIR directamente habria tres caminos distintos y tres
sitios donde corregir cada error de mapeo. Agregar una cuarta sede
manana es escribir un parser mas, sin tocar nada del resto.

Es el patron de "modelo de datos canonico" que nombra la plantilla.
"""

import json
import normalizador


class MensajeClinico:
    """
    Contenedor de datos. Guarda los valores TAL COMO VIENEN de la
    sede, sin normalizar: eso lo hace despues el normalizador.
    """

    def __init__(self):
        # Procedencia
        self.sede = None            # IPS SINCELEJO / CARTAGENA / COROZAL
        self.formato = None         # HL7 / CSV / JSON
        self.tipo_mensaje = None    # ADT^A01 / ORU^R01 / CSV-ADT
        self.id_mensaje = None

        # Paciente (valores crudos)
        self.documento = None
        self.nombres = None
        self.apellidos = None
        self.fecha_nac_cruda = None
        self.sexo_crudo = None

        # Atencion
        self.fecha_atencion_cruda = None
        self.tipo_atencion = None
        self.triage = 0
        self.causa_atencion = None

        # Diagnostico (codigo LOCAL, aun sin mapear a CIE-10)
        self.dx_codigo_local = None
        self.dx_descripcion = None

        # Laboratorio (nombre LOCAL, aun sin mapear a LOINC)
        self.lab_prueba_local = None
        self.lab_valor = None
        self.lab_unidad = None

        # None = valido. Con texto = motivo del rechazo.
        self.error_validacion = None

    def es_valido(self):
        """
        Valida ANTES de transformar. El enunciado marca como error
        frecuente "transformar sin validar": un mensaje invalido
        debe rechazarse con un motivo claro y quedar registrado,
        no perderse ni colarse a medias.
        """
        # Si el parser ya detecto un problema ESTRUCTURAL, se respeta
        # ese motivo en vez de sobrescribirlo con uno generico.
        if self.error_validacion is not None:
            return False

        # El nombre del campo depende del formato, para que el motivo
        # apunte a algo que exista de verdad en ese formato.
        if self.formato == "HL7":
            campo_doc = "PID-3"
            campo_nom = "PID-5"
        else:
            campo_doc = "campo 'documento'"
            campo_nom = "campo 'nombre'"

        if self.documento is None or len(str(self.documento).strip()) == 0:
            self.error_validacion = "Falta el documento del paciente (" + campo_doc + ")"
            return False

        if not normalizador.solo_digitos(str(self.documento).strip()):
            self.error_validacion = "El documento no es numerico: '" + str(self.documento) + "'"
            return False

        if self.apellidos is None or len(str(self.apellidos).strip()) == 0:
            self.error_validacion = "Falta el apellido del paciente (" + campo_nom + ")"
            return False

        if normalizador.normalizar_fecha(self.fecha_nac_cruda) is None:
            self.error_validacion = ("Fecha de nacimiento invalida o en formato "
                                     "desconocido: '" + str(self.fecha_nac_cruda) + "'")
            return False

        if self.sede is None or len(str(self.sede).strip()) == 0:
            self.error_validacion = "No se pudo determinar la sede de origen"
            return False

        self.error_validacion = None
        return True

    def resumen(self):
        return "[%s/%s] %s doc=%s id=%s" % (
            self.sede, self.formato, self.tipo_mensaje,
            self.documento, self.id_mensaje)


# ============================================================
#  HL7 v2.x
# ============================================================
#
#  HL7 v2 es texto plano posicional:
#    - segmentos separados por retorno de carro (\r)
#    - cada segmento empieza con 3 letras que dicen que es:
#        MSH cabecera, PID paciente, PV1 visita,
#        DG1 diagnostico, OBX resultado de laboratorio
#    - campos separados por  |
#    - componentes dentro del campo separados por  ^
#
#    PID|1||1098765432^^^HOSP^MR||Perez^Maria||19850722|F
#         ^           ^               ^          ^      ^
#      PID-1       PID-3           PID-5      PID-7  PID-8
#
#    PID-5 es 'Perez^Maria', asi que PID-5.1=Perez y PID-5.2=Maria
# ============================================================

def _campo(campos, n):
    """
    Campo numero n del segmento, o '' si no existe.

    Devolver '' en vez de lanzar error es deliberado: en HL7 los
    campos del final suelen venir ausentes y eso es NORMAL. Un
    mensaje corto sigue siendo valido.
    """
    if campos is None or n < 0 or n >= len(campos):
        return ""
    return campos[n].strip()


def _componente(campo, n):
    """
    Componente numero n de un campo, contando desde 1 para que
    coincida con la notacion HL7 (PID-5.1, PID-5.2...).
    """
    if campo is None or len(campo) == 0:
        return ""
    partes = campo.split("^")
    if n < 1 or n > len(partes):
        return ""
    return partes[n - 1].strip()


def parsear_hl7(texto, sede):
    """Convierte un mensaje HL7 v2 en un MensajeClinico."""
    m = MensajeClinico()
    m.sede = sede
    m.formato = "HL7"

    if texto is None or len(texto.strip()) == 0:
        m.error_validacion = "Mensaje HL7 vacio"
        return m

    # El estandar manda \r. Se aceptan tambien \n y \r\n porque
    # algunos sistemas legados los mandan mal, y rechazar por eso
    # seria rigido de mas.
    normalizado = texto.replace("\r\n", "\r").replace("\n", "\r")
    segmentos = normalizado.split("\r")

    for seg_bruto in segmentos:
        seg = seg_bruto.strip()
        if len(seg) < 3:
            continue                      # linea vacia o basura
        tipo = seg[0:3]
        c = seg.split("|")

        if tipo == "MSH":
            # MSH|^~\&|HIS|HOSP|HSB|FHIR|fecha||ADT^A01|MSG0001|P|2.5
            m.tipo_mensaje = _campo(c, 8)
            m.id_mensaje = _campo(c, 9)
            if m.fecha_atencion_cruda is None:
                m.fecha_atencion_cruda = _campo(c, 6)

        elif tipo == "PID":
            m.documento = _componente(_campo(c, 3), 1)
            nombre = _campo(c, 5)
            m.apellidos = _componente(nombre, 1)
            m.nombres = _componente(nombre, 2)
            m.fecha_nac_cruda = _componente(_campo(c, 7), 1)
            m.sexo_crudo = _componente(_campo(c, 8), 1)

        elif tipo == "PV1":
            # PV1-2 es la clase: E=urgencias, O=ambulatorio, I=internado
            clase = _componente(_campo(c, 2), 1)
            if clase.upper() == "E":
                m.tipo_atencion = "URGENCIAS"
            else:
                ubicacion = _componente(_campo(c, 3), 1)
                if "URGENCIA" in ubicacion.upper():
                    m.tipo_atencion = "URGENCIAS"
                else:
                    m.tipo_atencion = "CONSULTA EXTERNA"
            fecha_adm = _componente(_campo(c, 44), 1)
            if len(fecha_adm) > 0:
                m.fecha_atencion_cruda = fecha_adm

        elif tipo == "DG1":
            dx = _campo(c, 3)
            m.dx_codigo_local = _componente(dx, 1)
            m.dx_descripcion = _componente(dx, 2)

        elif tipo == "OBX":
            m.lab_prueba_local = _componente(_campo(c, 3), 1)
            m.lab_valor = _campo(c, 5)
            m.lab_unidad = _componente(_campo(c, 6), 1)

    if m.documento is None or len(m.documento) == 0:
        m.error_validacion = "El mensaje no trae segmento PID con documento"

    return m


# ============================================================
#  CSV  (sede 2 - Cartagena)
# ============================================================
#
#  Columnas esperadas:
#    documento, nombre_completo, fecha_nac, genero, fecha_atencion,
#    tipo_atencion, triage, dx_codigo, dx_descripcion,
#    lab_prueba, lab_valor, lab_unidad
# ============================================================

COLUMNAS_CSV = 12

COL_DOCUMENTO = 0
COL_NOMBRE = 1
COL_FECHA_NAC = 2
COL_GENERO = 3
COL_FECHA_ATENCION = 4
COL_TIPO_ATENCION = 5
COL_TRIAGE = 6
COL_DX_CODIGO = 7
COL_DX_DESCRIPCION = 8
COL_LAB_PRUEBA = 9
COL_LAB_VALOR = 10
COL_LAB_UNIDAD = 11


def separar_columnas(linea):
    """
    Parte una linea CSV RESPETANDO las comillas dobles.

    No se usa linea.split(',') porque un nombre puede traer una coma
    dentro de comillas:

        1098765432,"PEREZ GOMEZ, MARIA",22/07/1985
                   |------ un solo campo ------|

    Partir a lo bruto correria todas las columnas siguientes y
    produciria datos clinicos equivocados EN SILENCIO, que es peor
    que fallar.
    """
    resultado = []
    actual = []
    dentro_de_comillas = False

    for c in linea:
        if c == '"':
            dentro_de_comillas = not dentro_de_comillas
            continue                       # las comillas no son dato
        if c == ',' and not dentro_de_comillas:
            resultado.append("".join(actual).strip())
            actual = []
            continue
        actual.append(c)

    resultado.append("".join(actual).strip())
    return resultado


def _a_entero(texto, por_defecto):
    """
    Convierte a entero sin lanzar error. Un triage ilegible no debe
    tumbar el mensaje entero: es un dato secundario, a diferencia
    del documento, que si es obligatorio.
    """
    if texto is None:
        return por_defecto
    t = str(texto).strip()
    if not normalizador.solo_digitos(t):
        return por_defecto
    return int(t)


def parsear_csv(linea, sede):
    """Convierte UNA linea de CSV (sin cabecera) en un MensajeClinico."""
    m = MensajeClinico()
    m.sede = sede
    m.formato = "CSV"
    m.tipo_mensaje = "CSV-ADT"

    if linea is None or len(linea.strip()) == 0:
        m.error_validacion = "Linea CSV vacia"
        return m

    col = separar_columnas(linea)

    # Validacion ESTRUCTURAL antes de leer nada: si faltan columnas,
    # el resto de la lectura leeria valores corridos.
    if len(col) < COLUMNAS_CSV:
        m.error_validacion = ("La linea CSV tiene %d columnas y se esperaban %d"
                              % (len(col), COLUMNAS_CSV))
        return m

    m.documento = col[COL_DOCUMENTO]
    m.fecha_nac_cruda = col[COL_FECHA_NAC]
    m.sexo_crudo = col[COL_GENERO]

    nombre, apellidos = normalizador.separar_nombre(col[COL_NOMBRE])
    m.nombres = nombre
    m.apellidos = apellidos

    m.fecha_atencion_cruda = col[COL_FECHA_ATENCION]
    m.tipo_atencion = col[COL_TIPO_ATENCION]
    m.triage = _a_entero(col[COL_TRIAGE], 0)

    m.dx_codigo_local = col[COL_DX_CODIGO]
    m.dx_descripcion = col[COL_DX_DESCRIPCION]

    m.lab_prueba_local = col[COL_LAB_PRUEBA]
    m.lab_valor = col[COL_LAB_VALOR]
    m.lab_unidad = col[COL_LAB_UNIDAD]

    return m


# ============================================================
#  JSON  (sede 3 - Corozal)
# ============================================================

def parsear_json(texto, sede):
    """
    Convierte un objeto JSON legado en un MensajeClinico.

    La sede 3 ya usa nombres parecidos a FHIR (first_name, sex,
    birth_date), pero NO es FHIR: sigue siendo su modelo propio.
    Por eso tambien pasa por el modelo canonico en vez de enviarse
    directo.
    """
    m = MensajeClinico()
    m.sede = sede
    m.formato = "JSON"
    m.tipo_mensaje = "JSON-ADT"

    if texto is None or len(str(texto).strip()) == 0:
        m.error_validacion = "Mensaje JSON vacio"
        return m

    try:
        if isinstance(texto, dict):
            d = texto
        else:
            d = json.loads(texto)
    except Exception as e:
        m.error_validacion = "JSON mal formado: " + str(e)
        return m

    if not isinstance(d, dict):
        m.error_validacion = "Se esperaba un objeto JSON"
        return m

    m.documento = d.get("documento")
    m.nombres = d.get("first_name")
    m.apellidos = d.get("last_name")
    m.fecha_nac_cruda = d.get("birth_date")
    m.sexo_crudo = d.get("sex")

    m.fecha_atencion_cruda = d.get("fecha_atencion")
    m.tipo_atencion = d.get("tipo_atencion")
    m.triage = _a_entero(d.get("triage"), 0)
    m.causa_atencion = d.get("causa")

    m.dx_codigo_local = d.get("dx_codigo")
    m.dx_descripcion = d.get("dx_descripcion")

    m.lab_prueba_local = d.get("lab_prueba")
    m.lab_valor = d.get("lab_valor")
    m.lab_unidad = d.get("lab_unidad")

    return m
