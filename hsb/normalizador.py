"""
============================================================
 NORMALIZADOR A FHIR R4
============================================================

Convierte los datos crudos de las sedes legadas en recursos FHIR.
Cada sede guarda las cosas a su manera; FHIR exige una sola.

Esta escrito de forma explicita a proposito: bucles normales, ifs
normales y concatenacion de texto. Nada de comprensiones de lista
raras ni librerias de serializacion. Si hay que explicarlo linea
por linea en la sustentacion, se puede.

El JSON se arma con una lista de trozos y luego se une, en vez de
pegar cadenas con += dentro de un bucle (en Python eso crea una
cadena nueva en cada vuelta).
"""


# ============================================================
#  PARTE 1 - CONVERSIONES DE VALOR
# ============================================================

def solo_digitos(texto):
    """True si el texto tiene al menos un caracter y todos son digitos."""
    if texto is None:
        return False
    if len(texto) == 0:
        return False
    for c in texto:
        if c < '0' or c > '9':
            return False
    return True


# Dias de cada mes, de enero a diciembre. Febrero se corrige
# aparte cuando el ano es bisiesto.
DIAS_POR_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def es_bisiesto(anio):
    """
    Regla del calendario gregoriano: bisiesto cada 4 anos, salvo
    los multiplos de 100, salvo los multiplos de 400. Por eso 1900
    no fue bisiesto y 2000 si.
    """
    if anio % 4 != 0:
        return False
    if anio % 100 != 0:
        return True
    return anio % 400 == 0


def fecha_valida(anio, mes, dia):
    """
    Valida que la fecha exista de verdad en el calendario.

    Comprueba los dias que tiene cada mes, no solo que el dia este
    entre 1 y 31. La diferencia importa: una version anterior daba
    por buena una fecha de nacimiento del 31 de febrero, y una
    fecha imposible en una historia clinica es un dato falso que
    ya nadie vuelve a mirar.
    """
    if not solo_digitos(anio) or not solo_digitos(mes) or not solo_digitos(dia):
        return False
    a = int(anio)
    m = int(mes)
    d = int(dia)
    if a < 1900 or a > 2100:
        return False
    if m < 1 or m > 12:
        return False

    tope = DIAS_POR_MES[m - 1]
    if m == 2 and es_bisiesto(a):
        tope = 29
    if d < 1 or d > tope:
        return False
    return True


def normalizar_fecha(fecha):
    """
    Lleva la fecha de nacimiento de cualquier sede al formato que
    exige FHIR: ISO 8601, o sea AAAA-MM-DD.

        '19850722'    (sede 1, estilo HL7)  -> '1985-07-22'
        '22/07/1985'  (sede 2, local)       -> '1985-07-22'
        '1985-07-22'  (sede 3, ya ISO)      -> '1985-07-22'

    Devuelve None si no reconoce el formato o la fecha no existe.
    Devolver None es deliberado: es mejor que el bus rechace el
    mensaje con un motivo que inventarse una fecha clinica.
    """
    if fecha is None:
        return None
    f = str(fecha).strip()
    if len(f) == 0:
        return None

    # Caso A: '19850722' -> 8 digitos seguidos
    if len(f) == 8 and solo_digitos(f):
        anio = f[0:4]
        mes = f[4:6]
        dia = f[6:8]
        if not fecha_valida(anio, mes, dia):
            return None
        return anio + "-" + mes + "-" + dia

    # Caso B: '22/07/1985' -> separado por barras
    if len(f) == 10 and f[2] == '/' and f[5] == '/':
        dia = f[0:2]
        mes = f[3:5]
        anio = f[6:10]
        if not fecha_valida(anio, mes, dia):
            return None
        return anio + "-" + mes + "-" + dia

    # Caso C: '1985-07-22' -> ya viene en ISO, solo se valida
    if len(f) == 10 and f[4] == '-' and f[7] == '-':
        anio = f[0:4]
        mes = f[5:7]
        dia = f[8:10]
        if not fecha_valida(anio, mes, dia):
            return None
        return f

    return None


def normalizar_fecha_hora(valor):
    """
    Lleva una fecha CON HORA al formato dateTime de FHIR:
    AAAA-MM-DDTHH:MM:SS

        '20260310093000'       -> '2026-03-10T09:30:00'
        '15/05/2026 14:20'     -> '2026-05-15T14:20:00'
        '2026-08-02T10:45:00'  -> igual
        '2026-03-10 09:30:00'  -> '2026-03-10T09:30:00'
    """
    if valor is None:
        return None
    v = str(valor).strip()

    # Caso A: 14 digitos seguidos
    if len(v) == 14 and solo_digitos(v):
        if not fecha_valida(v[0:4], v[4:6], v[6:8]):
            return None
        return v[0:4] + "-" + v[4:6] + "-" + v[6:8] + "T" + v[8:10] + ":" + v[10:12] + ":" + v[12:14]

    # Caso B: '15/05/2026 14:20'
    if len(v) == 16 and v[2] == '/' and v[10] == ' ':
        if not fecha_valida(v[6:10], v[3:5], v[0:2]):
            return None
        return v[6:10] + "-" + v[3:5] + "-" + v[0:2] + "T" + v[11:13] + ":" + v[14:16] + ":00"

    # Caso C: ya viene en ISO, con T o con espacio
    if len(v) >= 19 and (v[10] == 'T' or v[10] == ' '):
        return v[0:10] + "T" + v[11:19]

    # Caso C2: ISO pero SIN segundos -> '2026-10-12 09:15'
    #
    # Es el formato que mandan de verdad las sedes 2 y 3, y antes
    # se caia por aqui: devolvia None y el Encounter se perdia sin
    # que nadie se enterara. Los segundos se completan con 00,
    # que no es inventar informacion clinica: la hora dada sigue
    # siendo exacta al minuto.
    if len(v) == 16 and v[4] == '-' and v[7] == '-' and \
            (v[10] == 'T' or v[10] == ' ') and v[13] == ':':
        if not fecha_valida(v[0:4], v[5:7], v[8:10]):
            return None
        return v[0:10] + "T" + v[11:16] + ":00"

    # Caso D: solo la fecha, sin hora
    solo_fecha = normalizar_fecha(v)
    if solo_fecha is not None:
        return solo_fecha + "T00:00:00"

    return None


def normalizar_genero(valor):
    """
    Traduce la codificacion de sexo de cada sede al vocabulario
    CERRADO de FHIR (administrative-gender).

    FHIR solo acepta: male, female, other, unknown.
    Cualquier otro valor invalida el recurso entero, por eso lo
    desconocido se mapea a 'unknown' en vez de dejarse pasar.
    """
    if valor is None:
        return "unknown"
    v = str(valor).strip().upper()

    if v in ("F", "FEMENINO", "FEMALE", "MUJER"):
        return "female"
    if v in ("M", "MASCULINO", "MALE", "HOMBRE"):
        return "male"
    if v in ("O", "OTRO", "OTHER"):
        return "other"
    return "unknown"


def separar_nombre(nombre_completo):
    """
    La sede 2 guarda 'MARIA PEREZ GOMEZ' en un solo campo, pero FHIR
    separa el nombre de pila (given) de los apellidos (family).

    Regla declarada: la PRIMERA palabra es el nombre, el resto son
    apellidos. Es una heuristica, no una verdad: con un nombre
    compuesto como 'MARIA JOSE PEREZ' falla. Queda documentado como
    limitacion en vez de fingir exactitud.

    Devuelve una tupla (nombre, apellidos).
    """
    if nombre_completo is None:
        return ("", "")
    n = str(nombre_completo).strip()
    if len(n) == 0:
        return ("", "")

    pos = n.find(' ')
    if pos < 0:
        return ("", n)          # una sola palabra: se toma como apellido
    return (n[0:pos], n[pos + 1:].strip())


def normalizar_clase_encuentro(tipo):
    """
    Traduce el tipo de atencion de la sede a la clase de Encounter
    de FHIR (sistema v3-ActCode).
        URGENCIAS        -> EMER
        CONSULTA EXTERNA -> AMB
    """
    if tipo is None:
        return "AMB"
    t = str(tipo).strip().upper()
    if "URGENCIA" in t or t == "EMERGENCY" or t == "EMER":
        return "EMER"
    return "AMB"


def escapar(texto):
    """
    Escapa los caracteres que romperian el JSON si se escribieran
    tal cual dentro de una cadena entre comillas.

    Sin esto, un apellido como  O"Brien  partiria el JSON en dos y
    HAPI rechazaria el mensaje entero.
    """
    if texto is None:
        return ""
    salida = []
    for c in str(texto):
        if c == '"':
            salida.append('\\"')
        elif c == '\\':
            salida.append('\\\\')
        elif c == '\n':
            salida.append('\\n')
        elif c == '\r':
            salida.append('\\r')
        elif c == '\t':
            salida.append('\\t')
        else:
            salida.append(c)
    return "".join(salida)


# ============================================================
#  PARTE 2 - CONSTRUCCION DE RECURSOS FHIR
# ============================================================

SISTEMA_DOCUMENTO = "urn:co:minsalud:documento"
SISTEMA_SEDE = "urn:red:ips:sede"


def construir_patient(documento, nombre, apellidos, fecha_nac, genero, sede):
    """Recurso Patient de FHIR R4."""
    p = []
    p.append('{')
    p.append('"resourceType":"Patient",')

    # El identificador es lo que permite reconocer al MISMO paciente
    # entre las tres sedes: todas usan el documento.
    p.append('"identifier":[{')
    p.append('"system":"' + SISTEMA_DOCUMENTO + '",')
    p.append('"value":"' + escapar(documento) + '"')
    p.append('}],')

    p.append('"name":[{')
    p.append('"use":"official",')
    p.append('"family":"' + escapar(apellidos) + '",')
    p.append('"given":["' + escapar(nombre) + '"]')
    p.append('}],')

    p.append('"gender":"' + escapar(genero) + '"')

    # birthDate solo si la fecha se pudo normalizar: escribir una
    # fecha invalida haria que HAPI rechace el recurso completo.
    if fecha_nac is not None:
        p.append(',"birthDate":"' + escapar(fecha_nac) + '"')

    # meta.tag guarda de que sede vino: trazabilidad para la
    # historia unificada ("este dato lo trajo Cartagena").
    p.append(',"meta":{"tag":[{')
    p.append('"system":"' + SISTEMA_SEDE + '",')
    p.append('"code":"' + escapar(sede) + '"')
    p.append('}]}')

    p.append('}')
    return "".join(p)


def construir_encounter(documento, fecha_inicio, clase, triage, sede):
    """Recurso Encounter: la atencion o visita."""
    p = []
    p.append('{')
    p.append('"resourceType":"Encounter",')
    p.append('"status":"finished",')

    p.append('"class":{')
    p.append('"system":"http://terminology.hl7.org/CodeSystem/v3-ActCode",')
    p.append('"code":"' + escapar(clase) + '"')
    p.append('},')

    # Se referencia al paciente por IDENTIFICADOR y no por id numerico,
    # porque el id lo asigna HAPI despues de crear el recurso.
    p.append('"subject":{"identifier":{')
    p.append('"system":"' + SISTEMA_DOCUMENTO + '",')
    p.append('"value":"' + escapar(documento) + '"')
    p.append('}},')

    if fecha_inicio is not None:
        p.append('"period":{"start":"' + escapar(fecha_inicio) + '"},')

    # El triage va como priority: es informacion clinica real que no
    # se puede perder en la conversion.
    p.append('"priority":{"coding":[{')
    p.append('"system":"urn:red:ips:triage",')
    p.append('"code":"' + escapar(str(triage)) + '"')
    p.append('}]},')

    p.append('"meta":{"tag":[{')
    p.append('"system":"' + SISTEMA_SEDE + '",')
    p.append('"code":"' + escapar(sede) + '"')
    p.append('}]}')

    p.append('}')
    return "".join(p)


def construir_condition(documento, codigo_cie10, descripcion, fecha, sede):
    """Recurso Condition: un diagnostico codificado en CIE-10."""
    p = []
    p.append('{')
    p.append('"resourceType":"Condition",')

    p.append('"clinicalStatus":{"coding":[{')
    p.append('"system":"http://terminology.hl7.org/CodeSystem/condition-clinical",')
    p.append('"code":"active"')
    p.append('}]},')

    p.append('"code":{"coding":[{')
    p.append('"system":"http://hl7.org/fhir/sid/icd-10",')
    p.append('"code":"' + escapar(codigo_cie10) + '",')
    p.append('"display":"' + escapar(descripcion) + '"')
    p.append('}]},')

    p.append('"subject":{"identifier":{')
    p.append('"system":"' + SISTEMA_DOCUMENTO + '",')
    p.append('"value":"' + escapar(documento) + '"')
    p.append('}}')

    if fecha is not None:
        p.append(',"recordedDate":"' + escapar(fecha) + '"')

    p.append(',"meta":{"tag":[{')
    p.append('"system":"' + SISTEMA_SEDE + '",')
    p.append('"code":"' + escapar(sede) + '"')
    p.append('}]}')

    p.append('}')
    return "".join(p)


def construir_observation(documento, codigo_loinc, descripcion,
                          valor, unidad, fecha, sede):
    """Recurso Observation: un resultado de laboratorio en LOINC."""
    p = []
    p.append('{')
    p.append('"resourceType":"Observation",')
    p.append('"status":"final",')

    p.append('"category":[{"coding":[{')
    p.append('"system":"http://terminology.hl7.org/CodeSystem/observation-category",')
    p.append('"code":"laboratory"')
    p.append('}]}],')

    p.append('"code":{"coding":[{')
    p.append('"system":"http://loinc.org",')
    p.append('"code":"' + escapar(codigo_loinc) + '",')
    p.append('"display":"' + escapar(descripcion) + '"')
    p.append('}]},')

    p.append('"subject":{"identifier":{')
    p.append('"system":"' + SISTEMA_DOCUMENTO + '",')
    p.append('"value":"' + escapar(documento) + '"')
    p.append('}},')

    if fecha is not None:
        p.append('"effectiveDateTime":"' + escapar(fecha) + '",')

    # valueQuantity lleva el numero Y su unidad. Un valor sin unidad
    # no significa nada en clinica: 182 mg/dL de glucosa no es lo
    # mismo que 182 mmol/L.
    p.append('"valueQuantity":{')
    p.append('"value":' + str(valor) + ',')
    p.append('"unit":"' + escapar(unidad) + '",')
    p.append('"system":"http://unitsofmeasure.org"')
    p.append('},')

    p.append('"meta":{"tag":[{')
    p.append('"system":"' + SISTEMA_SEDE + '",')
    p.append('"code":"' + escapar(sede) + '"')
    p.append('}]}')

    p.append('}')
    return "".join(p)


def construir_bundle(entradas):
    """
    Empaqueta varios recursos en un Bundle de tipo 'transaction'.

    POR QUE transaction Y NO collection:
    Un Bundle transaction le pide a HAPI que procese todas las
    entradas como UNA operacion atomica. O entran todas o no entra
    ninguna. Asi no queda un paciente creado sin su diagnostico.

    QUE ES ifNoneExist:
    Le dice a HAPI "crea este recurso SOLO si no existe ya uno que
    cumpla esta busqueda". Es la idempotencia a nivel de recurso:
    el mismo paciente llegando desde tres sedes distintas se
    consolida en un solo Patient.

    entradas: lista de diccionarios con las claves
              'recurso' (texto JSON), 'tipo' y opcional 'si_no_existe'
    """
    p = []
    p.append('{')
    p.append('"resourceType":"Bundle",')
    p.append('"type":"transaction",')
    p.append('"entry":[')

    escritos = 0
    for e in entradas:
        if e.get('recurso') is None:
            continue
        if escritos > 0:
            p.append(',')
        p.append('{')
        p.append('"resource":' + e['recurso'] + ',')
        p.append('"request":{')
        p.append('"method":"POST",')
        p.append('"url":"' + escapar(e['tipo']) + '"')
        if e.get('si_no_existe') is not None:
            p.append(',"ifNoneExist":"' + escapar(e['si_no_existe']) + '"')
        p.append('}')
        p.append('}')
        escritos += 1

    p.append(']')
    p.append('}')
    return "".join(p)
