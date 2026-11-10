# Guion de sustentación

**Cristian Gómez · Gerneidis Berrios**

15 minutos de demostración y 10 de preguntas. **La nota de sustentación es
individual: los dos tienen que poder explicar y modificar cualquier parte.** Esto es lo que hay que decir,
en qué orden, y qué responder a lo que suelen preguntar.

> **Antes de empezar.** La demostración se hace desde cero, como pide el
> enunciado. Ejecutar y esperar a que los siete contenedores estén arriba:
>
> ```bash
> docker compose down -v && docker compose up -d
> ```
>
> Tarda entre uno y dos minutos. Comprobar con `docker compose ps` que los
> siete aparecen, y abrir <http://localhost:8001/login>.

---

## La frase con la que se abre

> «Una red de IPS con tres sedes: Sincelejo, Cartagena y Corozal. Cada sede
> tiene su propio sistema y emite en un formato distinto, así que la historia
> clínica de un paciente está partida entre las tres. Lo que construí es la
> capa que la unifica **sin reemplazar ningún sistema legado**: las sedes
> siguen mandando lo que ya saben mandar, y un bus en el medio lo traduce
> todo a FHIR R4.»

Y enseguida la arquitectura (`docs/diagramas/05-arquitectura.svg`): seis
capas, cinco servicios transversales, y **cada capa tiene escrito el
requisito del enunciado que la justifica**. Esa última frase conviene decirla
en voz alta, porque el enunciado avisa de que un componente que no responde a
ningún RF o RNF está de más.

---

## El guion de la demo, paso por paso

El enunciado fija siete pasos. Son estos.

### 1. Arranque desde cero — RNF1

```bash
docker compose down -v && docker compose up -d
```

**Qué decir:** «Un solo comando. Levanta siete contenedores, carga los datos
sintéticos en los tres nodos y despliega el canal de Mirth automáticamente.
No hay ningún paso manual fuera del README.»

### 2. Cobertura FHIR en 0 % — RF6

Entrar como `drcarlos` / `medico.demo` → vista **Reporte de HC**.

**Qué decir:** «Los tres nodos tienen pacientes cargados, pero ninguno ha
pasado todavía por el bus, así que la cobertura de normalización a FHIR está
en cero. Este tablero es el que va a ir subiendo.»

### 3. Un mensaje HL7 v2 y uno CSV — RF1, RF2, RF3

```bash
bash tests/enviar-las-tres-sedes.sh
```

**Qué decir:** «El de Sincelejo entra como HL7 v2 ADT^A01 por MLLP al puerto
6661, que es donde escucha Mirth. Mirth responde el acuse de recibo y lo
reenvía al bus. El de Cartagena entra como CSV y el de Corozal como JSON,
los dos por HTTP. Los tres acaban en el mismo sitio.»

Volver al tablero: la cobertura subió. Y enseñar el Bundle:

```bash
curl -s "http://localhost:8080/fhir/Patient?identifier=urn:co:minsalud:documento|1098765432"
```

**El detalle que conviene señalar:** «Los tres formatos no se traducen
directamente a FHIR. Todos pasan primero por un modelo canónico, el
`MensajeClinico`. Son tres conversiones en vez de nueve, y hay un solo sitio
donde se decide cómo se escribe una fecha. Añadir una cuarta sede cuesta un
analizador y nada más.»

### 4. El mismo mensaje otra vez: no se duplica — RF3

```bash
bash tests/enviar-las-tres-sedes.sh
```

Responde `DUPLICADO`.

**Qué decir:** «La idempotencia no está en el código, está en la base de
datos: el hash SHA-256 del contenido es una restricción `UNIQUE`, y la
inserción es `ON CONFLICT DO NOTHING`.»

**Por qué así, si lo preguntan:** «Si lo hiciera consultando primero y
insertando después, entre las dos operaciones cabe otro hilo con el mismo
mensaje. La restricción única cierra esa ventana; una comprobación previa
no.»

**Y por qué el hash del contenido y no el identificador del mensaje:**
«Porque `MSH-10` lo reutilizan algunos sistemas antiguos al reiniciarse. El
hash del contenido no depende de que la sede se porte bien.»

### 5. Se cae una sede — RNF2

```bash
docker compose stop pg_nodo2
```

Recargar la vista: sigue respondiendo, marca el nodo 2 como no disponible y
avisa de que el resultado es parcial.

```bash
docker compose start pg_nodo2
```

Recargar: vuelve a estar completo. O ejecutar la prueba automática:

```bash
python3 tests/prueba-degradacion.py
```

**Qué decir:** «La consulta pregunta a los tres nodos, descarta los que no
responden y devuelve lo que haya, marcando el resultado como incompleto. Un
resultado parcial que se declara como parcial es útil; uno que se presenta
como completo es peligroso.»

### 6. Se altera un evento de auditoría: el verificador lo detecta — RF5

```bash
python3 tests/verificar-auditoria.py
```

**Qué decir:** «Cada evento guarda el hash del anterior:
`hash = SHA-256(contenido + hash_anterior)`. El script cambia un resultado
DENEGADO por PERMITIDO directamente en la base y el verificador señala la
fila exacta. Después borra una fila intermedia y el verificador da un
hallazgo distinto, de cadena rota, en la fila siguiente.»

### 7. Consulta unificada en las tres sedes — RF4

Vista **Médico** → buscar `1098765432`.

**Qué decir:** «Este paciente tiene registros en las tres sedes. Los datos
están fragmentados por documento en tres nodos PostgreSQL, y la consulta los
reúne. Quien consulta no sabe en qué nodo está el documento, y el sistema no
debería obligarle a saberlo.»

### Extra: accesos permitidos y denegados — RF5

```bash
python3 tests/prueba-roles.py
```

O en vivo: entrar como `maria` / `maria.demo` (paciente) y pulsar el botón
«probar acceso denegado», que pide la historia de otro documento.

**Qué decir:** «Hay tres niveles: autenticación, rol y **pertenencia**. El
documento de la paciente va firmado dentro del token, así que no basta con
cambiar el número en la dirección. Y esconder un botón no es seguridad:
quien llame al mismo endpoint con curl recibe el mismo 403.»

---

## Los cuatro usuarios de prueba

| Usuario | Clave | Rol | Qué ve |
|---|---|---|---|
| `maria` | `maria.demo` | paciente | Solo su propia historia |
| `admision1` | `admision.demo` | admisionista | Buscar y admitir, **sin** datos clínicos |
| `drcarlos` | `medico.demo` | medico | Historia completa y cobertura |
| `auditor1` | `auditor.demo` | auditor | Bitácora y verificación |

Son sintéticas y están en `infra/bus-schema.sql`.

---

## Las preguntas que van a hacer

### «Si la sede 2 cae a mitad de una transacción distribuida, ¿qué garantiza su diseño y qué sacrifica según CAP?»

Es la pregunta que el enunciado anuncia. La respuesta:

> «Elijo disponibilidad sobre consistencia, y lo hago explícito. Si el nodo 2
> no responde, la consulta no se bloquea: devuelve lo que tienen el 1 y el 3
> y **marca el resultado como parcial**, nombrando la sede caída. Sacrifico
> consistencia en el sentido de que el resultado puede no ser la foto
> completa en ese instante.
>
> Ahora, la atomicidad dentro de un nodo sí se conserva: el Bundle va como
> `transaction`, así que HAPI lo procesa entero o no lo procesa. Y el bus no
> pierde el mensaje: queda en la cola, se reintenta con retroceso exponencial
> y, si agota los intentos, va a la cola de mensajes muertos para reprocesarlo
> cuando el nodo vuelva. O sea: AP a nivel de consulta, con convergencia
> garantizada por la cola.»

### «¿Por qué Mirth y además un bus propio? ¿No sobra uno?»

> «Hacen cosas distintas. Mirth resuelve bien el protocolo: habla MLLP,
> responde el acuse y mantiene la conexión TCP con el sistema de la sede.
> Escribir eso desde cero sería reinventar algo resuelto. Pero su
> monitorización es limitada sin complementos, y el enunciado exige medir
> mensajes por minuto, latencia de extremo a extremo y porcentaje de
> fallidos. Así que Mirth es el adaptador de protocolo y el bus propio lleva
> la cola, la idempotencia, las terminologías y la bitácora. Cada uno donde
> es fuerte.»

### «¿Por qué el acuse de recibo se devuelve antes de hablar con FHIR?»

> «Porque si la sede tuviera que esperar a HAPI, una caída de HAPI pararía la
> admisión de pacientes en las tres sedes. Acoplaría la atención a la
> disponibilidad de un sistema que no es de la sede. El precio es que el bus
> se obliga a no perder el mensaje nunca, y de esa obligación nacen la cola,
> los reintentos y la cola de mensajes muertos.»

### «¿Por qué fragmentar por documento del paciente?»

> «Por el patrón de acceso: toda consulta clínica empieza por el documento.
> Si distribuyera por una columna que casi no se consulta, cada consulta
> tendría que preguntar a los tres nodos siempre. Los rangos están en
> `middleware.insertar_en_nodo_correcto`: menos de 4.000.000.000 al nodo 1,
> hasta 7.000.000.000 al nodo 2, el resto al nodo 3.»
>
> Y el matiz que distingue: «**Nodo y sede no son lo mismo.** El nodo lo
> determina el documento; la sede es el campo `entidad_salud` de la atención.
> Un paciente guardado en el nodo 1 puede tener atenciones en las tres sedes,
> y reunirlas es justamente la consulta unificada.»

### «¿Por qué `mensaje_bus`, `evento_auditoria` y `ref_terminologia` no están fragmentadas?»

> «Porque no pertenecen a ningún paciente, así que no hay clave por la que
> repartirlas. Y la bitácora además necesita un orden total estricto:
> repartirla entre tres nodos rompería la cadena de hash.»

### «Enséñeme dónde está eso en el código.»

Esto lo van a pedir — la rúbrica dice que hay que poder modificar en vivo.
Los sitios:

| Qué | Dónde |
|---|---|
| Analizadores de los tres formatos | `hsb/parsers.py` |
| Normalización a FHIR y Bundle | `hsb/normalizador.py` |
| Cola, idempotencia, reintentos, bitácora | `hsb/bus.py` |
| Token, PBKDF2, permisos por rol | `seguridad.py` |
| Consulta a los tres nodos y degradación | `middleware.py` |
| Las cuatro vistas y sus permisos | `portal.py` y `templates/portal.html` |
| Rangos de fragmentación | `middleware.py`, función `insertar_en_nodo_correcto` |

### «¿Qué falló mientras lo construía?»

Esta pregunta es una oportunidad, no una trampa. Hay cinco defectos
documentados en la sección de resultados del informe. El más instructivo:

> «El `Encounter` desaparecía en silencio para dos de las tres sedes. La
> función que normaliza fechas no reconocía el formato con hora pero sin
> segundos, devolvía vacío, y el código simplemente omitía el recurso.
> Llegaban el paciente y el diagnóstico, pero no la visita. Lo arreglé
> reconociendo ese formato, pero sobre todo cambiando el comportamiento: si
> la sede manda una fecha y no se puede interpretar, **el mensaje se rechaza**
> en lugar de seguir sin la atención. Perder datos sin avisar es peor que
> rechazar el mensaje.»

Y uno que encontró una prueba, no yo:

> «El validador de fechas aceptaba el 31 de febrero. Comprobaba que el día
> estuviera entre 1 y 31, no cuántos días tiene cada mes. Lo encontró una
> prueba unitaria que escribí precisamente para comprobar lo que el informe
> afirmaba. La lección es que una afirmación sobre el comportamiento del
> sistema no vale hasta que hay una prueba que la ejecuta.»

### «¿Qué limitaciones tiene?»

Decirlas antes de que las encuentren:

- Los datos son sintéticos y el volumen pequeño: **no hubo pruebas de carga**,
  así que la latencia medida no es extrapolable a producción.
- El token firmado **no se puede revocar** antes de que caduque. Es la
  consecuencia directa de no tener estado central; se mitiga con vigencia
  corta.
- Separar el nombre completo del CSV en nombres y apellidos es una
  **heurística** que falla con los nombres compuestos. La solución de verdad
  es pedirle a la sede los campos separados.
- La bitácora depende de que haya **un solo escritor**. Con varios, el orden
  total deja de estar garantizado y la cadena pierde sentido.

---

## Si algo falla en vivo

- **Un contenedor no arranca:** `docker compose ps` para ver cuál, y
  `docker compose logs <servicio> --tail 40`.
- **Mirth tarda:** es el más lento en arrancar (hasta dos minutos). Si el
  puerto 6661 aún no responde, seguir con las sedes 2 y 3 por HTTP y volver.
- **El tablero no carga:** comprobar `curl -s localhost:8001/health` y
  `curl -s localhost:8002/health`. El primero distingue entre `degradado` y
  `caido`.
- **Sale 401 en todo:** el token caduca a los 60 minutos. Volver a entrar.

---

## Lo que hay que haber hecho antes de la sustentación

- [ ] Crear el repositorio propio y subirlo con la etiqueta `v1.0`.
- [ ] Probar el arranque desde cero **una vez entera**, cronometrando.
- [ ] Leer este guion en voz alta una vez.
