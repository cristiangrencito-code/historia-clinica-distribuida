#!/usr/bin/env python3
"""
============================================================
 GENERADOR DE LOS DIAGRAMAS UML  (entregable de la Fase 1)
============================================================

Dibuja los cuatro diagramas que pide el enunciado:

  1. Casos de uso      (actores y que puede hacer cada uno)
  2. Secuencia         (el recorrido de un mensaje HL7)
  3. Clases            (las entidades del sistema)
  4. Estados           (por donde pasa un mensaje en el bus)

POR QUE UN SCRIPT Y NO UNA HERRAMIENTA DE DIBUJO:
no hace falta instalar nada (ni plantuml, ni graphviz, ni
node), se regeneran con un comando en cualquier maquina, y si
el diseno cambia se corrige el codigo y no se vuelve a dibujar
a mano. El SVG es texto, asi que ademas se puede versionar en
git y se ve que cambio entre una version y otra.

    python3 docs/diagramas/generar-diagramas.py

Solo usa la biblioteca estandar.
"""

import os


SALIDA = os.path.dirname(os.path.abspath(__file__))

# Paleta. Se define una vez para que los cuatro diagramas se
# vean de la misma familia.
AZUL = "#1b5e8f"
AZUL_SUAVE = "#e8f1f8"
VERDE = "#1d7a46"
VERDE_SUAVE = "#e6f4ec"
ROJO = "#a62828"
ROJO_SUAVE = "#fbeaea"
AMBAR = "#8a5a00"
AMBAR_SUAVE = "#fdf3e0"
GRIS = "#5c6b7a"
GRIS_SUAVE = "#f1f4f6"
BORDE = "#c3ccd4"
TINTA = "#1f2933"

FUENTE = "font-family='Segoe UI, Helvetica, Arial, sans-serif'"


# ============================================================
#  PIEZAS DE DIBUJO
# ============================================================

def escapar(t):
    """El SVG es XML: hay que escapar los caracteres especiales."""
    t = str(t)
    t = t.replace("&", "&amp;")
    t = t.replace("<", "&lt;")
    t = t.replace(">", "&gt;")
    return t


def texto(x, y, t, tam=11, color=TINTA, ancla="start", peso="normal",
          cursiva=False):
    estilo = ""
    if cursiva:
        estilo = " font-style='italic'"
    return ("<text x='%s' y='%s' %s font-size='%s' fill='%s' "
            "text-anchor='%s' font-weight='%s'%s>%s</text>"
            % (x, y, FUENTE, tam, color, ancla, peso, estilo, escapar(t)))


def caja(x, y, ancho, alto, relleno="#ffffff", borde=BORDE, radio=6,
         grosor=1, guiones=None):
    d = ""
    if guiones is not None:
        d = " stroke-dasharray='%s'" % guiones
    return ("<rect x='%s' y='%s' width='%s' height='%s' rx='%s' "
            "fill='%s' stroke='%s' stroke-width='%s'%s/>"
            % (x, y, ancho, alto, radio, relleno, borde, grosor, d))


def linea(x1, y1, x2, y2, color=GRIS, grosor=1, guiones=None, punta=None):
    d = ""
    if guiones is not None:
        d = " stroke-dasharray='%s'" % guiones
    m = ""
    if punta is not None:
        m = " marker-end='url(#%s)'" % punta
    return ("<line x1='%s' y1='%s' x2='%s' y2='%s' stroke='%s' "
            "stroke-width='%s'%s%s/>" % (x1, y1, x2, y2, color, grosor, d, m))


def elipse(cx, cy, rx, ry, relleno=AZUL_SUAVE, borde=AZUL):
    return ("<ellipse cx='%s' cy='%s' rx='%s' ry='%s' fill='%s' "
            "stroke='%s' stroke-width='1.3'/>" % (cx, cy, rx, ry, relleno, borde))


def monigote(x, y, nombre, color=AZUL):
    """El actor de UML: un monigote de palitos."""
    p = []
    p.append("<circle cx='%s' cy='%s' r='8' fill='none' stroke='%s' "
             "stroke-width='1.8'/>" % (x, y, color))
    p.append(linea(x, y + 8, x, y + 28, color, 1.8))
    p.append(linea(x - 12, y + 16, x + 12, y + 16, color, 1.8))
    p.append(linea(x, y + 28, x - 10, y + 44, color, 1.8))
    p.append(linea(x, y + 28, x + 10, y + 44, color, 1.8))
    p.append(texto(x, y + 60, nombre, 11.5, color, "middle", "600"))
    return "".join(p)


def cabecera(ancho, alto, titulo, subtitulo):
    """Marco comun: fondo, flechas definidas y titulo."""
    p = []
    p.append("<svg xmlns='http://www.w3.org/2000/svg' width='%s' "
             "height='%s' viewBox='0 0 %s %s'>" % (ancho, alto, ancho, alto))
    p.append("<defs>")
    # Punta de flecha rellena (asociacion, transicion)
    p.append("<marker id='punta' viewBox='0 0 10 10' refX='9' refY='5' "
             "markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
             "<path d='M 0 0 L 10 5 L 0 10 z' fill='%s'/></marker>" % GRIS)
    p.append("<marker id='puntaAzul' viewBox='0 0 10 10' refX='9' refY='5' "
             "markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
             "<path d='M 0 0 L 10 5 L 0 10 z' fill='%s'/></marker>" % AZUL)
    p.append("<marker id='puntaRoja' viewBox='0 0 10 10' refX='9' refY='5' "
             "markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
             "<path d='M 0 0 L 10 5 L 0 10 z' fill='%s'/></marker>" % ROJO)
    p.append("<marker id='puntaVerde' viewBox='0 0 10 10' refX='9' refY='5' "
             "markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
             "<path d='M 0 0 L 10 5 L 0 10 z' fill='%s'/></marker>" % VERDE)
    # Punta abierta (mensaje de respuesta)
    p.append("<marker id='puntaAbierta' viewBox='0 0 10 10' refX='9' refY='5' "
             "markerWidth='8' markerHeight='8' orient='auto-start-reverse'>"
             "<path d='M 0 0 L 10 5 L 0 10' fill='none' stroke='%s' "
             "stroke-width='1.4'/></marker>" % GRIS)
    # Rombo vacio (agregacion)
    p.append("<marker id='rombo' viewBox='0 0 12 12' refX='11' refY='6' "
             "markerWidth='11' markerHeight='11' orient='auto-start-reverse'>"
             "<path d='M 0 6 L 6 2 L 12 6 L 6 10 z' fill='#fff' "
             "stroke='%s'/></marker>" % GRIS)
    p.append("</defs>")
    p.append("<rect width='%s' height='%s' fill='#ffffff'/>" % (ancho, alto))
    p.append(texto(24, 32, titulo, 17, TINTA, "start", "650"))
    p.append(texto(24, 51, subtitulo, 11.5, GRIS))
    p.append(linea(24, 62, ancho - 24, 62, BORDE, 1))
    return "".join(p)


def guardar(nombre, partes):
    partes.append("</svg>")
    ruta = os.path.join(SALIDA, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))
    print("  %s" % nombre)


# ============================================================
#  1. DIAGRAMA DE CASOS DE USO
# ============================================================

def diagrama_casos_de_uso():
    A, H = 1060, 790
    p = [cabecera(A, H, "Diagrama de casos de uso",
                  "Quien puede hacer que. Los actores de la izquierda son "
                  "personas; el de la derecha es un sistema")]

    # Frontera del sistema
    p.append(caja(215, 84, 630, 600, "#fcfdfe", BORDE, 10, 1.5))
    p.append(texto(530, 106, "Plataforma de Interoperabilidad en Salud",
                   12.5, GRIS, "middle", "600"))

    # --- Casos de uso ---
    # Dos columnas, y los actores a cada lado de SU columna. Asi
    # ninguna linea de asociacion cruza por encima de otro caso
    # de uso, que es lo que vuelve ilegible un diagrama de estos.
    casos = [
        # columna izquierda: lo que hacen las personas
        (370, 165, "Ver mi historia", AZUL_SUAVE, AZUL),
        (370, 240, "Buscar paciente", AZUL_SUAVE, AZUL),
        (370, 315, "Registrar admision", AZUL_SUAVE, AZUL),
        (370, 390, "Ver historia completa", AZUL_SUAVE, AZUL),
        # columna derecha: la maquina y la auditoria
        (690, 165, "Ingerir mensaje clinico", VERDE_SUAVE, VERDE),
        (690, 240, "Normalizar a FHIR R4", VERDE_SUAVE, VERDE),
        (690, 315, "Reprocesar desde la DLQ", VERDE_SUAVE, VERDE),
        (690, 390, "Consultar bitacora", ROJO_SUAVE, ROJO),
        (690, 465, "Verificar la cadena de hash", ROJO_SUAVE, ROJO),
        # centrado abajo: lo alcanzan los dos lados
        (530, 540, "Ver tablero de cobertura", AZUL_SUAVE, AZUL),
    ]
    centro = {}
    for x, y, t, relleno, borde in casos:
        ancho = max(66, len(t) * 3.5 + 22)
        p.append(elipse(x, y, ancho, 23, relleno, borde))
        p.append(texto(x, y + 4, t, 10.5, borde, "middle", "600"))
        centro[t] = (x, y, ancho)

    # --- Casos de uso transversales ---
    p.append(caja(245, 592, 570, 76, "#fffdfa", "#e8cf9a", 8, 1.2, "6,4"))
    p.append(texto(530, 610, "transversales: los incluye TODO caso de uso",
                   10, AMBAR, "middle", "600"))
    for x, t in [(385, "Autenticarse"), (680, "Registrar en bitacora")]:
        ancho = max(66, len(t) * 3.5 + 22)
        p.append(elipse(x, 638, ancho, 21, AMBAR_SUAVE, AMBAR))
        p.append(texto(x, 642, t, 10.5, AMBAR, "middle", "600"))
        centro[t] = (x, 638, ancho)

    # --- Actores ---
    for x, y, n, c in [(85, 150, "Paciente", AZUL),
                       (85, 270, "Admisionista", AZUL),
                       (85, 390, "Medico", AZUL)]:
        p.append(monigote(x, y, n, c))

    p.append(monigote(975, 150, "Sistema de sede", VERDE))
    p.append(texto(975, 224, "(Mirth)", 10, VERDE, "middle"))
    p.append(monigote(975, 390, "Auditor", ROJO))

    # --- Asociaciones actor -> caso de uso ---
    def unir(ax, ay, nombre, color=GRIS):
        cx, cy, cw = centro[nombre]
        lado = cx - cw if ax < cx else cx + cw
        return linea(ax, ay, lado, cy, color, 1.1)

    p.append(unir(100, 178, "Ver mi historia"))
    p.append(unir(100, 298, "Buscar paciente"))
    p.append(unir(100, 298, "Registrar admision"))
    p.append(unir(100, 418, "Buscar paciente"))
    p.append(unir(100, 418, "Ver historia completa"))
    p.append(unir(100, 418, "Ver tablero de cobertura"))

    p.append(unir(960, 178, "Ingerir mensaje clinico", VERDE))
    p.append(unir(960, 418, "Consultar bitacora", ROJO))
    p.append(unir(960, 418, "Verificar la cadena de hash", ROJO))
    p.append(unir(960, 418, "Ver tablero de cobertura", ROJO))

    # --- include (solo el que no cruza nada) ---
    x1, y1, _ = centro["Ingerir mensaje clinico"]
    x2, y2, _ = centro["Normalizar a FHIR R4"]
    p.append(linea(x1, y1 + 23, x2, y2 - 23, AMBAR, 1.1, "5,4", "punta"))
    p.append(texto(x1 + 8, (y1 + y2) / 2.0 + 3, "<<include>>", 9, AMBAR,
                   "start", "normal", True))

    # Los dos transversales, con una sola flecha cada uno desde la
    # caja: dibujar un <<include>> desde cada caso de uso llenaria
    # el diagrama de lineas cruzadas y no anadiria informacion.
    # (no se dibuja una flecha por caso de uso: el rotulo de la
    #  caja ya dice que los incluyen todos, y veinte lineas
    #  cruzadas no anadirian nada)

    # --- Nota explicativa ---
    p.append(caja(24, 700, A - 48, 62, AMBAR_SUAVE, "#e8cf9a", 6))
    p.append(texto(40, 720,
                   "Autenticarse y Registrar en bitacora son transversales: "
                   "no hay manera de leer una historia clinica sin estar "
                   "identificado y sin", 10.4, AMBAR))
    p.append(texto(40, 737,
                   "dejar rastro. El apunte en la bitacora se hace tambien "
                   "cuando el acceso se DENIEGA, que es precisamente el caso "
                   "que hay que poder", 10.4, AMBAR))
    p.append(texto(40, 753,
                   "demostrar despues ante una auditoria.", 10.4, AMBAR))

    guardar("01-casos-de-uso.svg", p)


# ============================================================
#  2. DIAGRAMA DE SECUENCIA
# ============================================================

def diagrama_secuencia():
    A, H = 1180, 1000
    p = [cabecera(A, H, "Diagrama de secuencia",
                  "Recorrido de un mensaje HL7 v2 ADT^A01 desde la sede "
                  "hasta FHIR, con el camino del fallo")]

    participantes = [
        (110, "Sede 1\nSincelejo", AZUL),
        (290, "Mirth\nConnect", VERDE),
        (470, "HSB\n(bus)", VERDE),
        (640, "bus_db\ncola+bitacora", GRIS),
        (820, "HAPI\nFHIR R4", AZUL),
        (1010, "nodo1\nPostgreSQL", GRIS),
    ]

    base_y = 90
    fin_y = 880

    for x, nombre, color in participantes:
        a, b = nombre.split("\n")
        p.append(caja(x - 70, base_y, 140, 42,
                      "#ffffff", color, 6, 1.4))
        p.append(texto(x, base_y + 18, a, 11.5, color, "middle", "650"))
        p.append(texto(x, base_y + 33, b, 9.5, GRIS, "middle"))
        p.append(linea(x, base_y + 42, x, fin_y, BORDE, 1, "4,4"))

    def mensaje(y, desde, hasta, etiqueta, color=GRIS, punta="punta",
                guiones=None, nota=None):
        s = []
        x1 = participantes[desde][0]
        x2 = participantes[hasta][0]
        s.append(linea(x1, y, x2, y, color, 1.3, guiones, punta))
        mx = (x1 + x2) / 2.0
        s.append(texto(mx, y - 7, etiqueta, 10.3, color, "middle", "600"))
        if nota is not None:
            s.append(texto(mx, y + 13, nota, 9.3, GRIS, "middle"))
        return "".join(s)

    def auto(y, quien, etiqueta, color=GRIS, nota=None):
        """Mensaje de un participante a si mismo."""
        x = participantes[quien][0]
        s = []
        s.append(linea(x, y, x + 42, y, color, 1.3))
        s.append(linea(x + 42, y, x + 42, y + 24, color, 1.3))
        s.append(linea(x + 42, y + 24, x, y + 24, color, 1.3, None, "punta"))
        s.append(texto(x + 50, y + 6, etiqueta, 10.3, color, "start", "600"))
        if nota is not None:
            s.append(texto(x + 50, y + 20, nota, 9.3, GRIS, "start"))
        return "".join(s)

    # Coordenadas escritas una a una, no acumuladas con +=: asi se
    # ve de un vistazo donde cae cada mensaje y nada se sale del
    # dibujo.
    p.append(mensaje(175, 0, 1, "1. ADT^A01 por MLLP:6661", AZUL, "puntaAzul",
                     None, "VT + mensaje + FS CR"))
    p.append(mensaje(218, 1, 0, "2. ACK  MSA|AA", VERDE, "puntaAbierta", "5,4",
                     "se responde YA, sin esperar a FHIR"))
    p.append(mensaje(262, 1, 2, "3. POST /ingesta/hl7 + X-Sede-Clave", VERDE,
                     "puntaVerde"))
    p.append(auto(298, 2, "4. hash = SHA-256(contenido)", GRIS,
                  "la identidad del mensaje es su contenido"))
    p.append(mensaje(355, 2, 3, "5. INSERT ... ON CONFLICT DO NOTHING", GRIS,
                     "punta", None, "la idempotencia la impone el UNIQUE"))
    p.append(mensaje(398, 3, 2, "6. reservado / duplicado", GRIS,
                     "puntaAbierta", "5,4"))
    p.append(auto(430, 2, "7. validar -> modelo canonico", GRIS,
                  "RECHAZADO si falta el documento o la fecha no es legible"))
    p.append(mensaje(488, 2, 3, "8. SELECT ref_terminologia", GRIS, "punta",
                     None, "DM2 -> CIE-10 E11      HBA1C -> LOINC 4548-4"))
    p.append(auto(522, 2, "9. construir Bundle FHIR R4", VERDE,
                  "Patient + Encounter + Condition + Observation"))
    p.append(mensaje(580, 2, 4, "10. POST Bundle (transaction)", VERDE,
                     "puntaVerde", None, "Patient con ifNoneExist"))

    # --- Fragmento alt: los dos finales posibles ---
    alt_x, alt_w = 398, 672
    alt_y, alt_h = 600, 268
    p.append(caja(alt_x, alt_y, alt_w, alt_h, "none", ROJO, 6, 1.2, "6,4"))
    p.append(caja(alt_x, alt_y, 70, 18, ROJO_SUAVE, ROJO, 0, 1))
    p.append(texto(alt_x + 35, alt_y + 13, "alt", 10, ROJO, "middle", "700"))
    p.append(texto(alt_x + 80, alt_y + 13, "[HAPI no responde]", 9.5, ROJO))

    p.append(mensaje(644, 4, 2, "11a. error de conexion", ROJO,
                     "puntaAbierta", "5,4"))
    p.append(mensaje(684, 2, 3, "12a. estado=FALLIDO, proximo_intento=ahora+2^n",
                     ROJO, "puntaRoja", None,
                     "espera 2s, 4s, 8s... agotados los 8 intentos pasa a MUERTO"))

    # Separador del else
    p.append(linea(alt_x, 718, alt_x + alt_w, 718, ROJO, 1.1, "6,4"))
    p.append(texto(alt_x + 10, 734, "[else  -  HAPI responde]", 9.5, ROJO))

    p.append(mensaje(762, 4, 2, "11b. 201 + transaction-response", VERDE,
                     "puntaAbierta", "5,4", "de aqui sale Patient/1009"))

    p.append(mensaje(840, 2, 5, "12. UPDATE usuario SET fhir_patient_id",
                     GRIS, "punta", None,
                     "el id real de HAPI: es lo que mide el tablero de cobertura"))

    # Nota final
    p.append(caja(24, 902, A - 48, 76, AZUL_SUAVE, "#bcd6e8", 6))
    p.append(texto(40, 922,
                   "El ACK del paso 2 se manda ANTES de hablar con FHIR, y es "
                   "deliberado: la sede no puede quedarse bloqueada esperando a "
                   "un sistema que no", 10.5, AZUL))
    p.append(texto(40, 939,
                   "es suyo, y si lo hiciera, un fallo de HAPI pararia la "
                   "admision de pacientes en las tres sedes. A cambio, el bus se "
                   "obliga a no perder el", 10.5, AZUL))
    p.append(texto(40, 956,
                   "mensaje nunca: por eso existen la cola, los reintentos con "
                   "retroceso exponencial y la cola de mensajes muertos.",
                   10.5, AZUL))

    guardar("02-secuencia.svg", p)


# ============================================================
#  3. DIAGRAMA DE CLASES
# ============================================================

def diagrama_clases():
    A, H = 1240, 900
    p = [cabecera(A, H, "Diagrama de clases",
                  "Trece entidades repartidas en tres ambitos: el dominio "
                  "clinico, el bus y la seguridad")]

    def clase(x, y, nombre, atributos, color, ancho=210, estereotipo=None):
        alto = 30 + len(atributos) * 15 + 8
        if estereotipo is not None:
            alto += 13
        s = []
        s.append(caja(x, y, ancho, alto, "#ffffff", color, 5, 1.3))
        s.append("<path d='M %s %s h %s v 26 h -%s z' fill='%s' "
                 "stroke='%s' stroke-width='1.3'/>"
                 % (x, y + 5, ancho, ancho, color + "22", color))
        yy = y + 18
        if estereotipo is not None:
            s.append(texto(x + ancho / 2.0, y + 15, estereotipo, 8.5, GRIS,
                           "middle", "normal", True))
            yy = y + 30
        s.append(texto(x + ancho / 2.0, yy, nombre, 11.5, color, "middle", "650"))
        s.append(linea(x, yy + 8, x + ancho, yy + 8, color, 1))
        ty = yy + 23
        for a in atributos:
            peso = "650" if a.startswith("PK") or a.startswith("UK") else "normal"
            s.append(texto(x + 9, ty, a, 9.5, TINTA, "start", peso))
            ty += 15
        return "".join(s), alto

    # ---------- Ambito 1: dominio clinico ----------
    p.append(caja(24, 78, 560, 470, "#fbfdfe", BORDE, 8, 1.2, "6,4"))
    p.append(texto(40, 96, "DOMINIO CLINICO   ·   3 nodos fragmentados por documento",
                   10.5, AZUL, "start", "650"))

    s, _ = clase(44, 110, "Usuario", [
        "PK documento_id : bigint",
        "nombre_completo : varchar",
        "fecha_nacimiento : date",
        "sexo / genero : varchar",
        "municipio_residencia : varchar",
        "fhir_patient_id : varchar"], AZUL, 215)
    p.append(s)

    s, _ = clase(329, 110, "Atencion", [
        "PK atencion_id : serial",
        "FK documento_id : bigint",
        "entidad_salud : varchar  <- SEDE",
        "fecha_ingreso : timestamp",
        "entorno_atencion : varchar",
        "clasificacion_triage : varchar"], AZUL, 235)
    p.append(s)

    s, _ = clase(44, 290, "Diagnostico", [
        "PK diagnostico_id : serial",
        "FK atencion_id : int",
        "diagnostico_ingreso : varchar",
        "diagnostico_egreso : varchar"], AZUL, 215)
    p.append(s)

    s, _ = clase(329, 290, "TecnologiaSalud", [
        "PK tecnologia_id : uuid",
        "FK atencion_id : int",
        "FK id_personal_salud : uuid",
        "descripcion_medicamento : varchar",
        "dosis / frecuencia : varchar"], AZUL, 235)
    p.append(s)

    s, _ = clase(44, 405, "Egreso", [
        "PK egreso_id : serial",
        "FK atencion_id : int",
        "condicion_salida : varchar",
        "alergias : text"], AZUL, 215)
    p.append(s)

    s, _ = clase(329, 425, "ProfesionalSalud", [
        "PK id_personal_salud : uuid",
        "nombre : varchar",
        "especialidad : varchar"], AZUL, 235)
    p.append(s)

    # Relaciones del dominio
    p.append(linea(259, 170, 329, 170, GRIS, 1.2, None, "punta"))
    p.append(texto(294, 164, "1..*", 9, GRIS, "middle"))
    p.append(linea(151, 240, 151, 290, GRIS, 1.2, None, "punta"))
    p.append(linea(446, 240, 446, 290, GRIS, 1.2, None, "punta"))
    p.append(linea(151, 375, 151, 405, GRIS, 1.2, None, "punta"))
    p.append(linea(446, 390, 446, 425, GRIS, 1.2, None, "punta"))

    # ---------- Ambito 2: el bus ----------
    p.append(caja(606, 78, 610, 470, "#fbfefc", BORDE, 8, 1.2, "6,4"))
    p.append(texto(622, 96, "BUS DE INTEGRACION   ·   base bus_db, fuera de "
                            "la fragmentacion", 10.5, VERDE, "start", "650"))

    s, _ = clase(626, 110, "MensajeClinico", [
        "documento / nombres / apellidos",
        "fecha_nac_cruda : str",
        "fecha_atencion_cruda : str",
        "dx_codigo_local : str",
        "lab_prueba_local : str",
        "+ es_valido() : bool"], VERDE, 265, "modelo canonico, en memoria")
    p.append(s)

    s, _ = clase(926, 110, "MensajeBus", [
        "PK id : bigserial",
        "UK hash_mensaje : varchar(64)",
        "sede / formato : varchar",
        "estado : varchar",
        "intentos / max_intentos : int",
        "proximo_intento : timestamp",
        "contenido : text"], VERDE, 270)
    p.append(s)

    s, _ = clase(626, 305, "RefTerminologia", [
        "PK sistema : varchar",
        "PK codigo_local : varchar",
        "codigo_std : varchar",
        "descripcion : varchar"], VERDE, 265, "ConceptMap")
    p.append(s)

    s, _ = clase(926, 305, "BundleFHIR", [
        "type = transaction",
        "Patient  (ifNoneExist)",
        "Encounter",
        "Condition  (CIE-10)",
        "Observation  (LOINC)"], VERDE, 270, "recurso FHIR R4")
    p.append(s)

    s, _ = clase(626, 430, "EventoAuditoria", [
        "PK secuencia : bigserial",
        "usuario / rol / accion",
        "resultado : PERMITIDO|DENEGADO",
        "hash_anterior : varchar(64)",
        "hash_actual : varchar(64)"], ROJO, 265)
    p.append(s)

    p.append(linea(891, 170, 926, 170, GRIS, 1.2, None, "punta"))
    p.append(linea(758, 245, 758, 305, GRIS, 1.2, "5,4", "punta"))
    p.append(texto(766, 278, "traduce con", 9, GRIS))
    p.append(linea(891, 400, 926, 400, GRIS, 1.2, "5,4", "punta"))

    # La cadena de la bitacora, dibujada
    p.append(linea(891, 490, 920, 490, ROJO, 1.4, None, "puntaRoja"))
    p.append(texto(928, 487, "hash_actual del evento n", 9, ROJO))
    p.append(texto(928, 500, "es el hash_anterior del n+1", 9, ROJO))

    # ---------- Ambito 3: seguridad ----------
    p.append(caja(24, 566, 1192, 160, "#fffdfa", BORDE, 8, 1.2, "6,4"))
    p.append(texto(40, 584, "SEGURIDAD   ·   quien entra y que puede hacer",
                   10.5, AMBAR, "start", "650"))

    s, _ = clase(44, 598, "UsuarioSistema", [
        "PK usuario : varchar",
        "rol : varchar",
        "sal : varchar",
        "clave_hash : varchar  (PBKDF2)",
        "documento_id : bigint  (solo paciente)"], AMBAR, 250)
    p.append(s)

    s, _ = clase(334, 598, "TokenJWT", [
        "cabecera : {alg: HS256}",
        "datos : {usuario, rol, documento_id}",
        "exp / iat : epoch",
        "firma : HMAC-SHA256"], AMBAR, 250, "no se guarda, se firma")
    p.append(s)

    s, _ = clase(624, 598, "Rol", [
        "paciente | admisionista",
        "medico | auditor",
        "sistema_sede"], AMBAR, 230, "enumeracion")
    p.append(s)

    s, _ = clase(884, 598, "Permiso", [
        "VER_HC_PROPIA | VER_HC_COMPLETA",
        "VER_DATOS_ADMINISTRATIVOS",
        "BUSCAR_PACIENTE | INGESTAR",
        "VER_AUDITORIA | VER_COBERTURA"], AMBAR, 310, "enumeracion")
    p.append(s)

    p.append(linea(294, 660, 334, 660, GRIS, 1.2, None, "punta"))
    p.append(texto(314, 654, "emite", 9, GRIS, "middle"))
    p.append(linea(584, 660, 624, 660, GRIS, 1.2, None, "punta"))
    p.append(linea(854, 660, 884, 660, GRIS, 1.2, None, "punta"))
    p.append(texto(869, 654, "1..*", 9, GRIS, "middle"))

    # Relacion entre ambitos
    p.append(linea(151, 505, 151, 560, ROJO, 1.2, "5,4", "puntaRoja"))
    p.append(linea(758, 530, 758, 560, ROJO, 1.2, "5,4"))

    # Nota
    p.append(caja(24, 740, 1192, 48, GRIS_SUAVE, BORDE, 6))
    p.append(texto(40, 759,
                   "Por que MensajeBus, EventoAuditoria y RefTerminologia NO "
                   "estan fragmentados: los nodos se reparten por documento del "
                   "paciente, y estas tres", 10.3, TINTA))
    p.append(texto(40, 775,
                   "no pertenecen a ningun paciente. Ademas la bitacora "
                   "necesita un orden total estricto; repartirla rompería la "
                   "cadena de hash.", 10.3, TINTA))

    p.append(texto(24, 820, "El NODO lo decide el documento.  La SEDE la dice "
                            "atencion.entidad_salud.  Son dos cosas distintas: "
                            "un paciente del nodo1 puede",
                   10.5, AZUL, "start", "600"))
    p.append(texto(24, 838, "tener atenciones en las tres sedes, y esa es "
                            "justamente la consulta unificada que pide el RF4.",
                   10.5, AZUL, "start", "600"))

    guardar("03-clases.svg", p)


# ============================================================
#  4. DIAGRAMA DE ESTADOS
# ============================================================

def diagrama_estados():
    A, H = 1120, 756
    p = [cabecera(A, H, "Diagrama de estados de un mensaje en el bus",
                  "La columna mensaje_bus.estado. Los estados existen de "
                  "verdad en la base, no solo en el papel")]
    # Todo el cuerpo baja 34px: el bucle de DUPLICADO sube por
    # encima de RECIBIDO y se comia la linea del titulo.
    p.append("<g transform='translate(0,34)'>")

    def estado(x, y, nombre, nota, color, relleno, ancho=168):
        s = []
        s.append(caja(x, y, ancho, 52, relleno, color, 14, 1.5))
        s.append(texto(x + ancho / 2.0, y + 23, nombre, 12, color, "middle", "700"))
        s.append(texto(x + ancho / 2.0, y + 39, nota, 9, GRIS, "middle"))
        return "".join(s)

    def transicion(x1, y1, x2, y2, etiqueta, color=GRIS, punta="punta",
                   dx=0, dy=-6, ancla="middle"):
        s = [linea(x1, y1, x2, y2, color, 1.4, None, punta)]
        s.append(texto((x1 + x2) / 2.0 + dx, (y1 + y2) / 2.0 + dy,
                       etiqueta, 9.5, color, ancla, "600"))
        return "".join(s)

    # Estado inicial
    p.append("<circle cx='70' cy='144' r='9' fill='%s'/>" % TINTA)
    p.append(texto(70, 172, "llega", 9.5, GRIS, "middle"))

    # Camino feliz
    p.append(estado(110, 118, "RECIBIDO", "hash reservado", AZUL, AZUL_SUAVE))
    p.append(estado(350, 118, "VALIDADO", "estructura correcta", AZUL, AZUL_SUAVE))
    p.append(estado(590, 118, "TRANSFORMADO", "Bundle FHIR listo", AZUL, AZUL_SUAVE))
    p.append(estado(850, 118, "ENTREGADO", "en HAPI y en el nodo", VERDE, VERDE_SUAVE))

    p.append(transicion(278, 144, 350, 144, "valida"))
    p.append(transicion(518, 144, 590, 144, "convierte"))
    p.append(transicion(758, 144, 850, 144, "HTTP 2xx", VERDE, "puntaVerde"))

    # Estado final
    p.append("<circle cx='1060' cy='144' r='11' fill='none' stroke='%s' "
             "stroke-width='1.6'/>" % TINTA)
    p.append("<circle cx='1060' cy='144' r='6' fill='%s'/>" % TINTA)
    p.append(transicion(1018, 144, 1046, 144, "", VERDE, "puntaVerde"))

    # Duplicado: vuelve sobre si mismo
    p.append("<path d='M 150 118 q -10 -46 44 -46 q 54 0 44 46' fill='none' "
             "stroke='%s' stroke-width='1.4' stroke-dasharray='5,4' "
             "marker-end='url(#punta)'/>" % GRIS)
    p.append(texto(194, 64, "mismo hash -> DUPLICADO, no se procesa dos veces",
                   9.5, GRIS, "middle", "600"))

    # Rama de RECHAZO
    p.append(estado(350, 290, "RECHAZADO", "el mensaje esta mal", ROJO, ROJO_SUAVE))
    p.append(transicion(400, 170, 400, 290, "falta el documento,", ROJO,
                        "puntaRoja", -8, -14, "end"))
    p.append(texto(392, 242, "fecha ilegible", 9.5, ROJO, "end", "600"))
    p.append(transicion(650, 170, 530, 290, "no se puede convertir", ROJO,
                        "puntaRoja", 60, 6, "start"))

    # Rama de FALLO
    p.append(estado(590, 420, "FALLIDO", "el destino no responde", AMBAR,
                    AMBAR_SUAVE))
    p.append(estado(850, 420, "REINTENTANDO", "espera 2^n segundos", AMBAR,
                    AMBAR_SUAVE))
    p.append(estado(850, 560, "MUERTO", "agotados los intentos", ROJO,
                    ROJO_SUAVE))

    p.append(transicion(674, 170, 674, 420, "HAPI caido", AMBAR, "punta",
                        -8, 0, "end"))
    p.append(transicion(758, 446, 850, 446, "toca reintentar", AMBAR))

    # Reintento: vuelve a TRANSFORMADO
    p.append("<path d='M 934 420 q 0 -60 -60 -60 q -60 0 -60 -120' "
             "fill='none' stroke='%s' stroke-width='1.4' "
             "marker-end='url(#punta)'/>" % AMBAR)
    p.append(texto(946, 330, "intentos < 8: se reenvia", 9.5, AMBAR, "start",
                   "600"))

    p.append(transicion(934, 472, 934, 560, "intentos = 8", ROJO, "puntaRoja",
                        8, 0, "start"))

    # Reproceso manual desde la DLQ
    p.append("<path d='M 850 586 q -170 0 -170 -60 q 0 -40 -90 -40' "
             "fill='none' stroke='%s' stroke-width='1.4' "
             "stroke-dasharray='6,4' marker-end='url(#punta)'/>" % VERDE)
    p.append(texto(676, 600, "POST /reprocesar : el operador arregla la causa "
                             "y reencola", 9.5, VERDE, "middle", "600"))

    # Leyenda
    p.append(caja(24, 630, 1072, 62, GRIS_SUAVE, BORDE, 6))
    p.append(texto(40, 650, "RECHAZADO  y  MUERTO no son lo mismo, y es la "
                            "distincion que hace util a la cola:", 10.5, TINTA,
                   "start", "650"))
    p.append(texto(40, 667, "RECHAZADO = el mensaje esta mal. Reintentarlo "
                            "daria el mismo error, asi que NO se reintenta.",
                   10.2, ROJO))
    p.append(texto(40, 683, "MUERTO = el mensaje estaba bien pero el destino "
                            "fallo. Es un problema de infraestructura: se "
                            "reintento 8 veces y queda para revision manual.",
                   10.2, AMBAR))

    p.append("</g>")
    guardar("04-estados.svg", p)


# ============================================================
#  5. DIAGRAMA DE ARQUITECTURA
# ============================================================

def diagrama_arquitectura():
    """La arquitectura por capas. Cada capa lleva escrito el requisito
    del enunciado al que responde: el enunciado advierte que un
    componente que no responde a ningun RF o RNF esta de mas."""
    A = 1240
    AL = 1082
    p = [cabecera(A, AL, "Arquitectura de la plataforma de interoperabilidad",
                  "Seis capas y cinco servicios transversales. Cada capa "
                  "indica el requisito del enunciado que la justifica")]

    X1, X2, X3 = 140, 425, 710   # columnas del area principal
    ANCHO_C = 250
    DER = 960                    # borde derecho del area principal
    TX, TA = 975, 241            # columna transversal

    def banda(y, alto, numero, titulo, rf, color):
        """Etiqueta de capa, en el margen izquierdo."""
        q = [caja(24, y, 106, alto, "#ffffff", BORDE, 6, 1, "3,3")]
        q.append(texto(77, y + 20, "CAPA %s" % numero, 9.5, GRIS, "middle",
                       "650"))
        q.append(texto(77, y + 38, titulo, 10.5, TINTA, "middle", "600"))
        q.append(texto(77, y + 57, rf, 10.5, color, "middle", "700"))
        return "".join(q)

    def flecha(x, y1, y2, color=GRIS, etiqueta=None, punta="punta"):
        q = [linea(x, y1, x, y2, color, 1.6, None, punta)]
        if etiqueta is not None:
            q.append(texto(x + 9, (y1 + y2) / 2.0 + 4, etiqueta, 9.5, color))
        return "".join(q)

    def partir(t, n):
        """Parte un parrafo en lineas de como mucho n caracteres."""
        lineas, actual = [], ""
        for w in t.split():
            if actual and len(actual) + len(w) + 1 > n:
                lineas.append(actual)
                actual = w
            else:
                actual = (actual + " " + w).strip()
        if actual:
            lineas.append(actual)
        return lineas

    # ---------- CAPA 1: sedes legadas ----------
    p.append(banda(85, 92, "1", "Sedes", "RF1", AZUL))
    sedes = [
        (X1, "Sede 1  -  Sincelejo", "Sistema legado propio",
         "HL7 v2:  ADT^A01  /  ORU^R01"),
        (X2, "Sede 2  -  Cartagena", "Sistema legado propio",
         "Archivo CSV de admision"),
        (X3, "Sede 3  -  Corozal", "Sistema legado propio",
         "Archivo JSON de admision"),
    ]
    for x, titulo, sub, formato in sedes:
        p.append(caja(x, 85, ANCHO_C, 92, AZUL_SUAVE, AZUL, 6, 1.3))
        p.append(texto(x + 14, 108, titulo, 12, AZUL, "start", "650"))
        p.append(texto(x + 14, 127, sub, 10, GRIS))
        p.append(caja(x + 14, 137, ANCHO_C - 28, 28, "#ffffff", AZUL, 4))
        p.append(texto(x + 24, 155, formato, 10, TINTA, "start", "600"))

    # ---------- CAPA 2: ingesta ----------
    p.append(banda(215, 80, "2", "Ingesta", "RF1", AZUL))
    for x in (X1, X2, X3):
        p.append(flecha(x + 125, 177, 213, AZUL, None, "puntaAzul"))

    entradas = [
        (X1, "Mirth Connect 4.5.2", "Escucha MLLP en el puerto 6661",
         "Responde ACK^AA y reenvia por HTTP"),
        (X2, "POST /ingesta/csv", "Cabecera X-Sede-Clave o token JWT",
         "Lote de filas separadas por ;"),
        (X3, "POST /ingesta/json", "Cabecera X-Sede-Clave o token JWT",
         "Objeto por atencion"),
    ]
    for x, titulo, l1, l2 in entradas:
        p.append(caja(x, 215, ANCHO_C, 80, "#ffffff", AZUL, 6, 1.3))
        p.append(texto(x + 14, 238, titulo, 11.5, AZUL, "start", "650"))
        p.append(texto(x + 14, 257, l1, 9.8, GRIS))
        p.append(texto(x + 14, 273, l2, 9.8, GRIS))

    # ---------- CAPA 3: el HSB ----------
    p.append(banda(330, 150, "3", "HSB", "RF3", VERDE))
    for x in (X1, X2, X3):
        p.append(flecha(x + 125, 295, 328, VERDE, None, "puntaVerde"))

    p.append(caja(X1, 330, DER - X1, 150, VERDE_SUAVE, VERDE, 8, 1.6))
    p.append(texto(X1 + 16, 354, "Bus de servicios de salud  -  hsb/bus.py  "
                                 "(FastAPI, puerto 8002)", 12.5, VERDE,
                   "start", "650"))

    paso_ancho = 148
    pasos = [("1. Recepcion", "se guarda crudo"),
             ("2. Validacion", "obligatorios"),
             ("3. Transformacion", "Bundle FHIR R4"),
             ("4. Enrutamiento", "por sede"),
             ("5. Entrega", "cola + reintentos")]
    for i, (titulo, sub) in enumerate(pasos):
        x = X1 + i * (paso_ancho + 20)
        p.append(caja(x, 368, paso_ancho, 46, "#ffffff", VERDE, 5))
        p.append(texto(x + paso_ancho / 2.0, 387, titulo, 10.2, TINTA,
                       "middle", "650"))
        p.append(texto(x + paso_ancho / 2.0, 403, sub, 9.3, GRIS, "middle"))
        if i < 4:
            p.append(linea(x + paso_ancho, 391, x + paso_ancho + 18, 391,
                           VERDE, 1.4, None, "puntaVerde"))

    p.append(caja(X1 + 16, 426, DER - X1 - 32, 42, "#ffffff", VERDE, 5))
    p.append(texto(X1 + 28, 444, "Idempotencia:  hash SHA-256 del contenido "
                                 "declarado UNIQUE en la base  -  "
                                 "ON CONFLICT DO NOTHING", 9.8, TINTA))
    p.append(texto(X1 + 28, 460, "Reintentos con retroceso exponencial  -  "
                                 "cola de mensajes muertos (DLQ) tras 8 "
                                 "intentos  -  tabla mensaje_bus", 9.8, GRIS))

    # ---------- CAPA 4: almacenamiento ----------
    p.append(banda(515, 130, "4", "Datos", "RF2 RF4", AMBAR))
    p.append(flecha(X1 + 125, 480, 513, AMBAR, "Bundle FHIR", "punta"))
    p.append(flecha(X2 + 250, 480, 513, AMBAR, "filas del modelo local",
                    "punta"))

    p.append(caja(X1, 515, ANCHO_C, 130, AMBAR_SUAVE, AMBAR, 6, 1.3))
    p.append(texto(X1 + 14, 538, "HAPI FHIR R4", 12, AMBAR, "start", "650"))
    p.append(texto(X1 + 14, 556, "Servidor de referencia, puerto 8080", 9.8,
                   GRIS))
    for i, r in enumerate(["Patient", "Encounter", "Condition  (CIE-10)",
                           "Observation  (LOINC)"]):
        p.append(texto(X1 + 22, 578 + i * 16, "- " + r, 9.8, TINTA))
    p.append(texto(X1 + 14, 638, "Bundle type=transaction, ifNoneExist", 9.3,
                   GRIS, "start", "normal", True))

    p.append(caja(X2, 515, DER - X2, 130, AMBAR_SUAVE, AMBAR, 6, 1.3))
    p.append(texto(X2 + 14, 538, "Base de datos distribuida  -  fragmentacion "
                                 "horizontal por documento del paciente", 12,
                   AMBAR, "start", "650"))
    # Los rangos son los de middleware.insertar_en_nodo_correcto:
    # si se cambian ahi, hay que cambiarlos aqui.
    nodos = [("nodo1", "pg_nodo1", "doc < 4.000.000.000"),
             ("nodo2", "pg_nodo2", "4.000.000.000 - 6.999.999.999"),
             ("nodo3", "pg_nodo3", "doc >= 7.000.000.000")]
    nodo_ancho = (DER - X2 - 28 - 20) / 3.0
    for i, (n, cont, rango) in enumerate(nodos):
        x = X2 + 14 + i * (nodo_ancho + 10)
        p.append(caja(x, 552, nodo_ancho, 58, "#ffffff", AMBAR, 5))
        p.append(texto(x + nodo_ancho / 2.0, 571, n, 10.5, TINTA, "middle",
                       "650"))
        p.append(texto(x + nodo_ancho / 2.0, 586, cont, 9.3, GRIS, "middle"))
        p.append(texto(x + nodo_ancho / 2.0, 601, rango, 8.6, AMBAR, "middle"))
    p.append(texto(X2 + 14, 626, "PostgreSQL 15. Clave elegida por el patron "
                                 "de acceso: toda consulta empieza por el "
                                 "documento.", 9.5, GRIS))
    p.append(texto(X2 + 14, 639, "mensaje_bus, evento_auditoria y "
                                 "ref_terminologia NO se fragmentan: no "
                                 "pertenecen a ningun paciente.", 9.5, GRIS))

    # ---------- CAPA 5: API y middleware ----------
    p.append(banda(680, 78, "5", "API", "RF4", GRIS))
    p.append(flecha(X1 + 125, 645, 678, GRIS, None, "punta"))
    p.append(flecha(X2 + 250, 645, 678, GRIS, None, "punta"))

    p.append(caja(X1, 680, DER - X1, 78, GRIS_SUAVE, GRIS, 6, 1.4))
    p.append(texto(X1 + 16, 703, "API FastAPI  (app.py + portal.py)  y  "
                                 "middleware coordinador  (middleware.py)  -  "
                                 "puerto 8001", 12, TINTA, "start", "650"))
    p.append(texto(X1 + 16, 722, "Consulta unificada: pregunta a los tres "
                                 "nodos, une los resultados y devuelve una "
                                 "sola historia clinica.", 9.8, GRIS))
    p.append(texto(X1 + 16, 738, "Degradacion parcial (RNF2): si un nodo no "
                                 "responde, se descarta, la respuesta se "
                                 "marca como incompleta y se nombra la sede "
                                 "caida.", 9.8, ROJO))

    # ---------- CAPA 6: vistas ----------
    p.append(banda(793, 92, "6", "Vistas", "RF6", AZUL))
    for i in range(4):
        p.append(flecha(X1 + 95 + i * 210, 758, 791, AZUL, None, "puntaAzul"))

    vistas = [("Paciente", "Solo su propia HC", "El documento sale del token"),
              ("Admisionista", "Buscar y admitir", "Sin datos clinicos"),
              ("Medico", "HC completa", "Diagnosticos y labs"),
              ("Reporte de HC", "Cobertura por sede", "Latencia y fallidos")]
    for i, (titulo, l1, l2) in enumerate(vistas):
        x = X1 + i * 210
        p.append(caja(x, 793, 190, 92, AZUL_SUAVE, AZUL, 6, 1.3))
        p.append(texto(x + 95, 818, titulo, 11.8, AZUL, "middle", "650"))
        p.append(texto(x + 95, 840, l1, 9.8, TINTA, "middle"))
        p.append(texto(x + 95, 857, l2, 9.3, GRIS, "middle"))

    # ---------- TRANSVERSALES ----------
    p.append(caja(TX, 85, TA, 800, "#ffffff", ROJO, 8, 1.6, "5,4"))
    p.append(texto(TX + TA / 2.0, 110, "SERVICIOS TRANSVERSALES", 10.5, ROJO,
                   "middle", "700"))
    p.append(texto(TX + TA / 2.0, 128, "atraviesan las seis capas", 9.5, GRIS,
                   "middle", "normal", True))

    def bloque(y, titulo, sub, lineas, relleno, borde, color_titulo):
        """Cada bloque crece segun el numero de lineas: asi ningun
        texto se sale de su caja."""
        alto = 58 + len(lineas) * 12.5 + 6
        q = [caja(TX + 14, y, TA - 28, alto, relleno, borde, 6)]
        q.append(texto(TX + 26, y + 22, titulo, 12, color_titulo, "start",
                       "650"))
        q.append(texto(TX + 26, y + 39, sub, 9.5, GRIS))
        for i, l in enumerate(lineas):
            if l:
                q.append(texto(TX + 26, y + 58 + i * 12.5, l, 9.3, TINTA))
        return "".join(q), alto

    transversales = [
        ("Seguridad", "RF5  -  seguridad.py",
         ["Token JWT firmado HMAC-SHA256.",
          "Claves con PBKDF2, 120.000",
          "iteraciones y sal por usuario.",
          "",
          "Tres niveles de control:",
          "1. autenticacion  (hay token?)",
          "2. rol  (el permiso existe?)",
          "3. pertenencia  (es suyo?)"],
         ROJO_SUAVE, ROJO, ROJO),
        ("Bitacora encadenada", "RF5  -  evento_auditoria",
         ["Cada evento guarda el hash",
          "del anterior:",
          "hash = SHA-256(contenido +",
          "          hash_anterior)",
          "",
          "Alterar una fila rompe la",
          "cadena; el verificador la",
          "senala."],
         ROJO_SUAVE, ROJO, ROJO),
        ("Observabilidad", "RNF3",
         ["/health  y  /metrics  en cada",
          "servicio.",
          "",
          "El bus mide: mensajes por",
          "minuto, latencia media y",
          "porcentaje de fallidos."],
         GRIS_SUAVE, GRIS, TINTA),
        ("Despliegue", "RNF1",
         ["docker compose up levanta",
          "los siete contenedores, carga",
          "los datos sinteticos y",
          "despliega el canal de Mirth."],
         AZUL_SUAVE, AZUL, AZUL),
        ("Terminologias", "RF3  -  ref_terminologia",
         ["20 correspondencias:",
          "DM2 -> E11,  HTA -> I10  (CIE-10)",
          "HBA1C -> 4548-4  (LOINC)",
          "CREATININA -> 2160-0"],
         AMBAR_SUAVE, AMBAR, AMBAR),
    ]
    y = 148
    for titulo, sub, lineas, relleno, borde, ct in transversales:
        svg, alto = bloque(y, titulo, sub, lineas, relleno, borde, ct)
        p.append(svg)
        y = y + alto + 10

    # ---------- NOTA FINAL ----------
    p.append(caja(24, 910, A - 48, 152, GRIS_SUAVE, BORDE, 6))
    p.append(texto(40, 932, "Por que cada pieza esta ahi", 11.5, TINTA,
                   "start", "650"))
    notas = [
        ("Los sistemas legados no se reemplazan.",
         "Cada sede sigue emitiendo en el formato que ya sabe producir. La "
         "plataforma traduce; no obliga a nadie a cambiar de sistema."),
        ("Mirth y un bus propio, no solo uno de los dos.",
         "Mirth habla MLLP y responde el ACK, que es trabajo de protocolo. El "
         "bus propio guarda la cola, el hash de idempotencia y la bitacora, "
         "que es trabajo de estado."),
        ("El ACK se devuelve antes de hablar con FHIR.",
         "Si la sede esperara a HAPI, una caida de HAPI detendria la admision "
         "en las tres sedes. El precio es que el bus se obliga a no perder el "
         "mensaje: de ahi la cola, los reintentos y la DLQ."),
        ("Tres nodos y no una sola base.",
         "Se fragmenta por documento porque toda consulta clinica empieza por "
         "el documento. Distribuir por una columna que no se consulta "
         "obligaria a preguntar siempre a los tres nodos."),
    ]
    for i, (titulo, cuerpo) in enumerate(notas):
        x = 40 if i % 2 == 0 else 630
        y = 958 if i < 2 else 1012
        p.append(texto(x, y, titulo, 9.8, AZUL, "start", "650"))
        for j, l in enumerate(partir(cuerpo, 104)[:3]):
            p.append(texto(x, y + 15 + j * 13, l, 9.3, TINTA))

    guardar("05-arquitectura.svg", p)


# ============================================================

if __name__ == "__main__":
    print("Generando diagramas UML en %s" % SALIDA)
    diagrama_casos_de_uso()
    diagrama_secuencia()
    diagrama_clases()
    diagrama_estados()
    diagrama_arquitectura()
    print("listo.")
