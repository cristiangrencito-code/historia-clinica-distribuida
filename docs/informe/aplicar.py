# -*- coding: utf-8 -*-
"""
Mete el contenido del informe dentro del XML de la plantilla,
conservando sus estilos.

Se reemplaza de mayor a menor indice para que los indices no se
desplacen al insertar parrafos nuevos.
"""

import re
import sys

sys.path.insert(0, ".")
from contenido import CONTENIDO, CENTRADO

RUTA = "unpacked/word/document.xml"

PPR_DEFECTO = ('<w:pPr><w:spacing w:after="120"/>'
               '<w:rPr><w:lang w:val="es-CO"/></w:rPr></w:pPr>')


def escapar(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def trozos(texto):
    """
    Parte el texto en (fragmento, negrita, cursiva).
    **asi** = negrita,  *asi* = cursiva.
    """
    salida = []
    i = 0
    actual = ""
    negrita = False
    cursiva = False
    while i < len(texto):
        if texto[i:i + 2] == "**":
            if actual:
                salida.append((actual, negrita, cursiva))
                actual = ""
            negrita = not negrita
            i += 2
        elif texto[i] == "*":
            if actual:
                salida.append((actual, negrita, cursiva))
                actual = ""
            cursiva = not cursiva
            i += 1
        else:
            actual += texto[i]
            i += 1
    if actual:
        salida.append((actual, negrita, cursiva))
    return salida


def construir(estilo, texto, ppr_original):
    """Devuelve el XML de un parrafo."""
    if estilo in (None, CENTRADO):
        ppr = ppr_original if ppr_original else PPR_DEFECTO
    elif estilo == "Listaconvietas":
        ppr = ('<w:pPr><w:pStyle w:val="Listaconvietas"/>'
               '<w:spacing w:after="60"/>'
               '<w:rPr><w:lang w:val="es-CO"/></w:rPr></w:pPr>')
    else:
        ppr = ('<w:pPr><w:pStyle w:val="%s"/>'
               '<w:rPr><w:lang w:val="es-CO"/></w:rPr></w:pPr>' % estilo)

    runs = []
    for frag, neg, cur in trozos(texto):
        rpr = "<w:rPr>"
        if neg:
            rpr += "<w:b/>"
        if cur:
            rpr += "<w:i/>"
        rpr += '<w:lang w:val="es-CO"/></w:rPr>'
        runs.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>'
                    % (rpr, escapar(frag)))

    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def main():
    x = open(RUTA, encoding="utf-8").read()

    # Localizar cada parrafo con su posicion exacta en el texto
    posiciones = [(m.start(), m.end(), m.group(0))
                  for m in re.finditer(r"<w:p[ >].*?</w:p>|<w:p/>", x, re.S)]
    print("parrafos en la plantilla:", len(posiciones))

    cambiados = 0
    anadidos = 0
    for indice in sorted(CONTENIDO.keys(), reverse=True):
        if indice >= len(posiciones):
            print("  AVISO: no existe el parrafo %d" % indice)
            continue
        ini, fin, viejo = posiciones[indice]

        m = re.search(r"<w:pPr>.*?</w:pPr>", viejo, re.S)
        ppr = m.group(0) if m else None

        nuevos = [construir(e, t, ppr) for e, t in CONTENIDO[indice]]
        x = x[:ini] + "".join(nuevos) + x[fin:]
        cambiados += 1
        anadidos += len(nuevos) - 1

    open(RUTA, "w", encoding="utf-8").write(x)
    print("parrafos reemplazados: %d  (+%d nuevos)" % (cambiados, anadidos))

    total = len(re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", x, re.S))
    print("parrafos resultantes:", total)


if __name__ == "__main__":
    main()
