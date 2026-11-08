# Tabla de mapeo de campos

Cómo viaja cada dato desde el formato de cada sede hasta FHIR R4.

Las tres sedes mandan cosas distintas, así que no se traduce de cada formato
a FHIR por separado: primero **todo** se lleva a un modelo intermedio
(`MensajeClinico`, en [`hsb/parsers.py`](../hsb/parsers.py)) y desde ahí se
construye el Bundle una sola vez, en
[`hsb/normalizador.py`](../hsb/normalizador.py).

Son tres conversiones en vez de nueve, y hay un solo sitio donde se decide
cómo se escribe una fecha o un género. Añadir una cuarta sede cuesta un
*parser* y nada más.

```
HL7 v2 ─┐
CSV ────┼──> MensajeClinico ──> Bundle FHIR R4
JSON ───┘      (canónico)
```

---

## Datos del paciente → `Patient`

| # | Sede 1 (HL7 v2) | Sede 2 (CSV) | Sede 3 (JSON) | Campo canónico | Destino FHIR | Transformación |
|---|---|---|---|---|---|---|
| 1 | `PID-3.1` | col 0 | `documento` | `documento` | `Patient.identifier[0].value` | Se le pone el `system` `urn:co:minsalud:documento` para que el número no sea ambiguo entre países |
| 2 | `PID-5.1` | col 1 (resto) | `last_name` | `apellidos` | `Patient.name[0].family` | En CSV el nombre viene en una sola celda; se parte por el primer espacio |
| 3 | `PID-5.2` | col 1 (1ª palabra) | `first_name` | `nombres` | `Patient.name[0].given[0]` | Heurística documentada: es imperfecta y se deja escrita a propósito |
| 4 | `PID-7.1` | col 2 | `birth_date` | `fecha_nac_cruda` | `Patient.birthDate` | `AAAAMMDD`, `DD/MM/AAAA` o ISO → `AAAA-MM-DD`. **Si no se puede leer, se devuelve vacío: nunca se inventa una fecha clínica** |
| 5 | `PID-8.1` | col 3 | `sex` | `sexo_crudo` | `Patient.gender` | `M`/`MASCULINO`/`male` → `male`; `F`/`FEMENINO` → `female`; lo demás → `unknown` |
| — | *(la sede)* | *(la sede)* | *(la sede)* | `sede` | `Patient.meta.tag` con `urn:red:ips:sede` | Queda marcado de qué sede vino el dato, que es lo que permite auditar después |

## Datos de la atención → `Encounter`

| # | Sede 1 (HL7 v2) | Sede 2 (CSV) | Sede 3 (JSON) | Campo canónico | Destino FHIR | Transformación |
|---|---|---|---|---|---|---|
| 6 | `MSH-9` | — | — | `tipo_mensaje` | *(no va a FHIR)* | `ADT^A01`, `ORU^R01`. Sirve para enrutar dentro del bus y queda en `mensaje_bus` |
| 7 | `MSH-10` | — | — | `id_mensaje` | *(no va a FHIR)* | **No se usa como clave de idempotencia**: algunos sistemas antiguos reutilizan los identificadores al reiniciarse |
| 8 | `PV1-44.1`, si no `MSH-7` | col 4 | `fecha_atencion` | `fecha_atencion_cruda` | `Encounter.period.start` | A `dateTime` de FHIR. Si viene una fecha y no se puede leer, **el mensaje se rechaza**: perder la atención en silencio sería peor |
| 9 | `PV1-2.1` + `PV1-3.1` | col 5 | `tipo_atencion` | `tipo_atencion` | `Encounter.class.code` | `E` (o una ubicación que diga *urgencias*) → `EMER`; todo lo demás → `AMB`, según `v3-ActCode` |
| 10 | — | col 6 | `triage` | `triage` | `Encounter.priority.coding` | No existe en FHIR un campo estándar de triage colombiano: se conserva con `system` propio `urn:red:ips:triage` antes que perderlo |
| 11 | `EVN-7` / texto libre | — | `causa` | `causa_atencion` | *(local)* | Se guarda en `atencion.causa_atencion` del nodo |

## Diagnóstico → `Condition`

| # | Sede 1 (HL7 v2) | Sede 2 (CSV) | Sede 3 (JSON) | Campo canónico | Destino FHIR | Transformación |
|---|---|---|---|---|---|---|
| 12 | `DG1-3.1` | col 7 | `dx_codigo` | `dx_codigo_local` | `Condition.code.coding[0].code` | **Se traduce a CIE-10** con `ref_terminologia`: `DM2`→`E11`, `HTA`→`I10`, `IAM`→`I21` |
| 13 | `DG1-3.2` | col 8 | `dx_descripcion` | `dx_descripcion` | `Condition.code.coding[0].display` | Texto tal cual |
| — | — | — | — | *(derivado)* | `Condition.clinicalStatus` | Fijo en `active`: ninguna de las tres sedes manda ese dato |
| — | `PID-3.1` | col 0 | `documento` | `documento` | `Condition.subject.identifier` | Se referencia **por identificador y no por id numérico**, porque el id lo asigna HAPI después |

## Laboratorio → `Observation`

| # | Sede 1 (HL7 v2) | Sede 2 (CSV) | Sede 3 (JSON) | Campo canónico | Destino FHIR | Transformación |
|---|---|---|---|---|---|---|
| 14 | `OBX-3.1` | col 9 | `lab_prueba` | `lab_prueba_local` | `Observation.code.coding[0].code` | **Se traduce a LOINC**: `GLUCOSA EN SANGRE`→`2339-0`, `HEMOGLOBINA GLICOSILADA`→`4548-4`, `CREATININA`→`2160-0` |
| 15 | `OBX-5` | col 10 | `lab_valor` | `lab_valor` | `Observation.valueQuantity.value` | Numérico |
| 16 | `OBX-6.1` | col 11 | `lab_unidad` | `lab_unidad` | `Observation.valueQuantity.unit` | `mg/dL`, `%`, `mg/L` |
| — | — | — | — | *(derivado)* | `Observation.status` | Fijo en `final` |
| — | — | — | — | *(derivado)* | `Observation.category` | Fijo en `laboratory` |
| — | *(fecha de atención)* | col 4 | `fecha_atencion` | `fecha_atencion_cruda` | `Observation.effectiveDateTime` | La misma fecha normalizada del `Encounter` |

**Total: 16 campos de origen mapeados**, más seis derivados que FHIR exige y
que ninguna sede envía.

---

## Las decisiones que hay que poder defender

**Una fecha ilegible no se inventa.** `normalizar_fecha` devuelve vacío
cuando no reconoce el formato, y el mensaje se rechaza con el motivo escrito.
Poner la fecha de hoy, o `1900-01-01`, metería un dato falso en una historia
clínica. Un mensaje rechazado se ve en la cola y se corrige; un dato falso no
se ve nunca más.

**El `system` de cada identificador importa tanto como el valor.** Un
`identifier` con valor `1098765432` y sin `system` no dice nada: podría ser
una cédula colombiana, un número de historia o un DNI de otro país. Con
`urn:co:minsalud:documento` el mismo número significa lo mismo en las tres
sedes, y por eso el `ifNoneExist` puede consolidar al paciente en vez de
duplicarlo.

**El triage se conserva aunque FHIR no tenga dónde ponerlo.** La alternativa
era descartarlo, y es información clínica real. Se guarda en
`Encounter.priority` con un `system` propio, que es exactamente lo que FHIR
espera que se haga con un vocabulario local.

**La separación de nombre en el CSV es una heurística, y está documentada
como tal.** `LAURA MEJIA ORTIZ` se parte en `given = LAURA` y
`family = MEJIA ORTIZ`. Funciona casi siempre y falla con los nombres
compuestos. La solución de verdad es pedirle a la sede que mande los campos
separados; mientras tanto, lo honesto es que la limitación esté escrita en el
código y no escondida.

**Lo que no cabe en FHIR va al nodo local.** `causa_atencion`,
`modalidad_entrega` o `via_ingreso` son del modelo colombiano de historia
clínica. Forzarlos dentro de un recurso FHIR estándar los volvería
irrecuperables; se quedan en la base del nodo, que es donde tienen sentido.
