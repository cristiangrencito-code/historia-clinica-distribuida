# Diagramas UML

Los cuatro diagramas que pide la Fase 1 del parcial.

Se generan con un script, no con una herramienta de dibujo:

```bash
python3 docs/diagramas/generar-diagramas.py
```

No hace falta instalar nada — ni plantuml, ni graphviz, ni node — y como el
SVG es texto, git enseña qué cambió entre una versión y otra.

| Archivo | Qué muestra |
|---|---|
| [`01-casos-de-uso.svg`](01-casos-de-uso.svg) | Cinco actores y doce casos de uso. Los dos transversales (autenticarse y registrar en bitácora) van aparte |
| [`02-secuencia.svg`](02-secuencia.svg) | Un ADT^A01 desde la sede hasta FHIR, con el fragmento `alt` de los dos finales posibles |
| [`03-clases.svg`](03-clases.svg) | Trece entidades en tres ámbitos: dominio clínico, bus y seguridad |
| [`04-estados.svg`](04-estados.svg) | Los estados de `mensaje_bus.estado`, que existen de verdad en la base |

## Qué defender de cada uno

**Casos de uso.** Los actores están repartidos a los dos lados, cada uno
junto a su columna, para que ninguna línea de asociación cruce por encima de
otro caso de uso. `Autenticarse` y `Registrar en bitácora` están en una caja
aparte porque los incluyen todos: no hay forma de leer una historia clínica
sin estar identificado y sin dejar rastro, y el apunte se hace también
**cuando el acceso se deniega**.

**Secuencia.** El ACK del paso 2 sale antes de hablar con FHIR. Es
deliberado: si la sede tuviera que esperar a FHIR, un fallo de HAPI pararía
la admisión de pacientes en las tres sedes. A cambio, el bus se obliga a no
perder el mensaje nunca, y de ahí salen la cola, los reintentos y la DLQ. El
fragmento `alt` muestra los dos finales: `FALLIDO` con reintento, o
`ENTREGADO`.

**Clases.** Tres ámbitos separados a propósito. `MensajeBus`,
`EventoAuditoria` y `RefTerminologia` **no** están fragmentados: los nodos se
reparten por documento del paciente y estas tres no pertenecen a ningún
paciente. Además la bitácora necesita un orden total estricto — repartirla
rompería la cadena de hash.

**Estados.** La distinción entre `RECHAZADO` y `MUERTO` es la que hace útil a
la cola. `RECHAZADO` es un mensaje mal formado: reintentarlo daría el mismo
error, así que no se reintenta. `MUERTO` es un mensaje correcto cuyo destino
falló: se reintentó ocho veces y queda para revisión manual.

## Para meterlos en el informe

Word 2016 en adelante y LibreOffice insertan SVG directamente
(*Insertar → Imagen*), y mantienen la nitidez al imprimir.

Si el informe se hace en LaTeX:

```latex
\usepackage{svg}
...
\includesvg[width=\textwidth]{docs/diagramas/01-casos-de-uso}
```

Y si en algún momento hace falta PNG, se abre el SVG en el navegador y se
exporta, o se usa `rsvg-convert` (paquete `librsvg2-bin`):

```bash
rsvg-convert -w 2200 docs/diagramas/01-casos-de-uso.svg -o 01-casos-de-uso.png
```
