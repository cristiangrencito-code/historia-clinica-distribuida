r"""
============================================================
 SEGURIDAD  -  TOKEN JWT FIRMADO Y PERMISOS POR ROL  (RF5)
============================================================

El enunciado pide "autenticacion con token (OAuth2/OIDC con
Keycloak o, como minimo, JWT firmado) y autorizacion por rol".

Aqui esta el JWT hecho a mano, con la biblioteca estandar de
Python y nada mas: hmac, hashlib, base64, json, time. No hay
magia escondida en una dependencia externa; cada paso se puede
explicar y se puede abrir con las manos.

QUE ES UN JWT
Son tres trozos de texto pegados con un punto:

    eyJhbGciOi...  .  eyJ1c3VhcmlvIj...  .  3K9fPq...
    \____________/    \________________/    \_______/
       cabecera            datos             firma
      (que algoritmo)   (quien eres)      (HMAC-SHA256)

Los dos primeros son JSON en base64url: CUALQUIERA los puede
leer. Un JWT NO cifra nada, solo garantiza que nadie lo
modifico. Por eso aqui no va nunca un dato clinico, solo el
usuario, su rol y la fecha de caducidad.

POR QUE ES STATELESS Y POR QUE NOS IMPORTA EN UN SISTEMA DISTRIBUIDO
La firma se calcula con un secreto compartido. Cualquier
servicio que tenga ese secreto puede comprobar el token EL SOLO,
sin preguntarle a nadie. El HSB emite el token y la app lo
valida en su propio proceso: no hay una llamada de red por
peticion, y si el emisor se cae, los servicios que ya tienen el
secreto siguen validando. Un token de sesion guardado en una
tabla haria lo contrario: un punto central que todos consultan
y que al caerse tumba la autenticacion de todo el sistema.

EL PRECIO QUE SE PAGA (hay que decirlo en la sustentacion)
Al no haber estado central, un token no se puede revocar antes
de que caduque. Se compensa con una vigencia corta (60 min).
Revocacion inmediata exigiria una lista negra compartida, que
es volver a tener estado central.
"""

import os
import json
import time
import hmac
import base64
import hashlib


# ============================================================
#  CONFIGURACION
# ============================================================

# El secreto con el que se firma. En produccion va en .env (que
# esta en .gitignore). El valor por defecto es de desarrollo y
# esta marcado como tal a proposito: si aparece en los logs, se
# ve de inmediato que nadie configuro el real.
SECRETO = os.getenv("JWT_SECRETO", "DESARROLLO-NO-USAR-EN-PRODUCCION")

VIGENCIA_MINUTOS = int(os.getenv("JWT_VIGENCIA_MINUTOS", "60"))

# Iteraciones de PBKDF2 para las claves de usuario. Mas
# iteraciones = mas lento probar claves a la fuerza bruta.
ITERACIONES_CLAVE = 120000


def usando_secreto_de_desarrollo():
    """Para que /health lo avise en voz alta."""
    return SECRETO == "DESARROLLO-NO-USAR-EN-PRODUCCION"


# ============================================================
#  BASE64URL
#
#  El base64 normal usa '+' y '/', que en una URL o en una
#  cabecera HTTP significan otra cosa. base64url los cambia por
#  '-' y '_', y quita el relleno '=' del final.
# ============================================================

def base64url_codificar(datos):
    """bytes -> texto base64url sin relleno."""
    texto = base64.urlsafe_b64encode(datos).decode("ascii")
    # Quitar el relleno manualmente, caracter a caracter desde
    # el final, para que se vea que es justo eso lo que pasa.
    while len(texto) > 0 and texto[-1] == "=":
        texto = texto[:-1]
    return texto


def base64url_decodificar(texto):
    """texto base64url sin relleno -> bytes."""
    # Hay que devolver el relleno: base64 trabaja en bloques de
    # 4 caracteres, asi que se completa hasta el multiplo de 4.
    faltan = len(texto) % 4
    if faltan == 2:
        texto = texto + "=="
    elif faltan == 3:
        texto = texto + "="
    elif faltan == 1:
        # Longitud imposible en base64: el token esta corrupto.
        raise ValueError("longitud base64url invalida")
    return base64.urlsafe_b64decode(texto.encode("ascii"))


# ============================================================
#  FIRMA
# ============================================================

def firmar(mensaje):
    """
    HMAC-SHA256 del mensaje con el secreto.

    Por que HMAC y no simplemente SHA-256(secreto + mensaje):
    el hash a secas es vulnerable al ataque de extension de
    longitud; un atacante puede anadir texto al final y calcular
    la firma nueva sin conocer el secreto. HMAC esta construido
    con dos pasadas de hash justamente para cerrar ese agujero.
    """
    return hmac.new(SECRETO.encode("utf-8"),
                    mensaje.encode("utf-8"),
                    hashlib.sha256).digest()


# ============================================================
#  CREAR Y VERIFICAR EL TOKEN
# ============================================================

def crear_token(usuario, rol, documento_id=None, minutos=None):
    """
    Devuelve el JWT como texto.

    documento_id solo se usa con el rol 'paciente': dice de que
    persona es la historia que ese usuario tiene derecho a ver.
    Va DENTRO del token y firmado, asi que el paciente no puede
    cambiarlo para espiar a otro (si lo cambia, la firma no
    cuadra y el token se rechaza).
    """
    if minutos is None:
        minutos = VIGENCIA_MINUTOS

    ahora = int(time.time())

    cabecera = {"alg": "HS256", "typ": "JWT"}
    datos = {
        "usuario": usuario,
        "rol": rol,
        "documento_id": documento_id,
        "iat": ahora,                       # emitido en
        "exp": ahora + (minutos * 60),      # caduca en
    }

    # separators sin espacios: el JSON tiene que ser identico
    # byte a byte al verificar, porque la firma se calcula sobre
    # el texto, no sobre el objeto.
    cab64 = base64url_codificar(
        json.dumps(cabecera, separators=(",", ":")).encode("utf-8"))
    dat64 = base64url_codificar(
        json.dumps(datos, separators=(",", ":")).encode("utf-8"))

    cuerpo = cab64 + "." + dat64
    firma64 = base64url_codificar(firmar(cuerpo))

    return cuerpo + "." + firma64


def verificar_token(token):
    """
    Comprueba el token y devuelve (valido, datos_o_motivo).

      (True,  {"usuario":..., "rol":..., ...})
      (False, "firma invalida")

    EL ORDEN DE LAS COMPROBACIONES IMPORTA:
    primero la firma, despues el contenido. Si se mirara el
    contenido antes de validar la firma, se estarian tomando
    decisiones con datos que el atacante escribio.
    """
    if not token:
        return (False, "no se envio token")

    # 1. Tiene que tener exactamente tres trozos
    trozos = token.split(".")
    if len(trozos) != 3:
        return (False, "el token no tiene tres partes")

    cab64 = trozos[0]
    dat64 = trozos[1]
    firma_recibida = trozos[2]

    # 2. Recalcular la firma con nuestro secreto
    try:
        firma_esperada = base64url_codificar(firmar(cab64 + "." + dat64))
    except Exception:
        return (False, "token mal formado")

    # compare_digest y no '==': la comparacion normal se para en
    # el primer caracter distinto, y el tiempo que tarda filtra
    # informacion sobre cuantos caracteres acerto el atacante
    # (ataque de temporizacion). compare_digest tarda lo mismo
    # siempre.
    if not hmac.compare_digest(firma_esperada, firma_recibida):
        return (False, "firma invalida: el token fue alterado")

    # 3. Ahora si, leer el contenido
    try:
        cabecera = json.loads(base64url_decodificar(cab64))
        datos = json.loads(base64url_decodificar(dat64))
    except Exception:
        return (False, "el contenido del token no es JSON valido")

    # 4. El algoritmo tiene que ser el que esperamos.
    #    Sin esta linea existe el ataque "alg: none": el atacante
    #    pone alg=none, borra la firma y entra. Nunca se confia
    #    en el algoritmo que declara el propio token.
    if cabecera.get("alg") != "HS256":
        return (False, "algoritmo no permitido")

    # 5. Caducidad
    if "exp" not in datos:
        return (False, "el token no declara caducidad")
    if int(time.time()) > int(datos["exp"]):
        return (False, "el token caduco")

    return (True, datos)


# ============================================================
#  CLAVES DE USUARIO
# ============================================================

def hash_clave(clave, sal):
    """
    Deriva la clave con PBKDF2-HMAC-SHA256.

    POR QUE NO UN SHA-256 PELADO:
      - La SAL (un texto distinto por usuario) hace que dos
        personas con la misma clave tengan hashes distintos, y
        deja inservibles las tablas precalculadas.
      - Las ITERACIONES hacen el calculo lento a proposito.
        Para quien inicia sesion una vez son milisegundos; para
        quien prueba millones de claves son anos.
    """
    derivada = hashlib.pbkdf2_hmac("sha256",
                                   clave.encode("utf-8"),
                                   sal.encode("utf-8"),
                                   ITERACIONES_CLAVE)
    return derivada.hex()


def clave_correcta(clave_escrita, sal, hash_guardado):
    """Compara en tiempo constante, por lo mismo que el token."""
    calculado = hash_clave(clave_escrita, sal)
    return hmac.compare_digest(calculado, hash_guardado)


# ============================================================
#  AUTORIZACION POR ROL  (RF5 y RF6)
#
#  Autenticar es saber QUIEN eres (el token).
#  Autorizar es saber QUE puedes hacer (esta tabla).
#  Son dos cosas distintas y el parcial pide las dos.
#
#  El criterio es el de minimo privilegio: cada rol tiene solo
#  lo que necesita para su trabajo. El admisionista registra
#  pacientes pero NO lee diagnosticos, porque para admitir a
#  alguien no hace falta saber que enfermedad tiene.
# ============================================================

PERMISOS = {
    "paciente": [
        "VER_HC_PROPIA",
    ],
    "admisionista": [
        "BUSCAR_PACIENTE",
        "VER_DATOS_ADMINISTRATIVOS",
        "REGISTRAR_ADMISION",
    ],
    "medico": [
        "BUSCAR_PACIENTE",
        "VER_DATOS_ADMINISTRATIVOS",
        "VER_HC_COMPLETA",
        "REGISTRAR_ATENCION",
        "VER_COBERTURA",
    ],
    "auditor": [
        "VER_AUDITORIA",
        "VERIFICAR_AUDITORIA",
        "VER_METRICAS",
        "VER_COBERTURA",
    ],
    # Rol de maquina: lo usan los sistemas de las sedes y Mirth
    # para empujar mensajes al bus. No puede leer historias.
    "sistema_sede": [
        "INGESTAR",
    ],
}


def puede(rol, accion):
    """True si ese rol tiene ese permiso. Recorrido explicito."""
    lista = PERMISOS.get(rol)
    if lista is None:
        return False
    for permitida in lista:
        if permitida == accion:
            return True
    return False


def extraer_token_de_cabecera(cabecera_authorization):
    """
    De 'Bearer eyJhbG...' saca 'eyJhbG...'.
    Devuelve None si la cabecera no viene o no es Bearer.
    """
    if not cabecera_authorization:
        return None
    partes = cabecera_authorization.split(" ")
    if len(partes) != 2:
        return None
    if partes[0].lower() != "bearer":
        return None
    return partes[1]
