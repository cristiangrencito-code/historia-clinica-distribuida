# Informe

`Informe_Plataforma_Interoperabilidad_Salud.docx` sigue la plantilla v7 del
curso, conservando sus estilos: se edito el documento original en vez de
recrearlo, de modo que los titulos, la tipografia y el formato son los que
puso el docente.

## Lo que falta por hacer a mano

1. **Completar los apellidos** en la portada, donde dice `[APELLIDOS]`.
2. **Insertar los cuatro diagramas.** En las secciones del modelado UML hay
   una linea que indica que diagrama va en cada sitio. En Word:
   *Insertar - Imagen - Este dispositivo*, y elegir el SVG correspondiente
   de `docs/diagramas/`. Word 2016 en adelante inserta SVG sin perder
   nitidez.

## Como se genero

El contenido vive en `contenido.py` y `aplicar.py` lo inserta en el XML de
la plantilla. Si hay que corregir un parrafo, se edita el contenido y se
vuelve a generar, en lugar de tocar el .docx a mano:

```bash
cp ../../../Plantilla_Proyecto_Interoperabilidad_v7.docx plantilla.docx
unzip -q plantilla.docx -d unpacked/
python3 aplicar.py
(cd unpacked && zip -XrD ../Informe_Plataforma_Interoperabilidad_Salud.docx .)
```

## Que contiene

Las secciones de la plantilla, rellenadas con el trabajo real del parcial.
Dos advertencias sobre el contenido heredado de la plantilla:

- Las secciones **VIABILIDAD TECNICA** e **INTEROPERABILIDAD BASADA EN
  DATOS** traian listados muy amplios (Kubernetes, Keycloak, SNOMED CT,
  Kafka, certificaciones ISO). Se conservaron porque describen la ruta a
  produccion, pero se anadio al principio de cada una un parrafo que separa
  explicitamente **lo que el prototipo implementa hoy** de **lo que queda
  como trabajo futuro**. Presentarlo todo como hecho seria falso.
- La seccion **AVANCE INICIAL** y la de **VALIDACION DE MODELOS UML** traian
  datos de ejemplo (Visual Paradigm, Figma, Spring Boot, "5 violaciones
  criticas"). Se reemplazaron por lo que de verdad se hizo.

Catorce referencias en APA 7.
