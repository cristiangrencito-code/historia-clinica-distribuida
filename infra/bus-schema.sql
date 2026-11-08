-- ============================================================
--  ESQUEMA DEL HSB (Health Service Bus)
--
--  El enunciado dice: "El equipo anade mensaje_bus,
--  evento_auditoria y ref_terminologia."
--
--  Viven en una base APARTE (bus_db) y no dentro de los nodos
--  fragmentados. Razon: los nodos estan particionados por
--  documento del paciente, pero estos datos no pertenecen a
--  ningun paciente concreto:
--    - mensaje_bus      es metadato del transporte
--    - evento_auditoria necesita un orden total estricto para
--                       que la cadena de hash sea verificable
--    - ref_terminologia es un catalogo global
--  Repartirlos por documento no tendria sentido y romperia la
--  cadena de auditoria.
-- ============================================================


-- ------------------------------------------------------------
--  1. MENSAJE_BUS  -  idempotencia, cola y reintentos (RF3)
-- ------------------------------------------------------------
CREATE TABLE mensaje_bus (
    id              BIGSERIAL PRIMARY KEY,

    -- CLAVE DE IDEMPOTENCIA: SHA-256 del contenido del mensaje.
    -- El UNIQUE es lo que impide de verdad procesar dos veces lo
    -- mismo. No basta con comprobarlo en el codigo: entre el
    -- SELECT y el INSERT podria colarse otro hilo. La garantia
    -- tiene que vivir donde esta el estado compartido.
    hash_mensaje    VARCHAR(64) UNIQUE NOT NULL,

    sede            VARCHAR(30),        -- IPS SINCELEJO / CARTAGENA / COROZAL
    formato         VARCHAR(10),        -- HL7 / CSV / JSON
    tipo_mensaje    VARCHAR(20),        -- ADT^A01 / ORU^R01 / CSV-ADT
    documento_id    BIGINT,             -- paciente al que se refiere

    -- Estados del diagrama de estados del UML (entregable Fase 1):
    --   RECIBIDO -> VALIDADO -> TRANSFORMADO -> ENTREGADO
    --        \-> RECHAZADO (invalido, no se reintenta)
    --        \-> FALLIDO -> REINTENTANDO -> ... -> MUERTO
    estado          VARCHAR(20) NOT NULL DEFAULT 'RECIBIDO',

    intentos        INT NOT NULL DEFAULT 0,
    max_intentos    INT NOT NULL DEFAULT 5,
    proximo_intento TIMESTAMP,          -- cuando reintentar (backoff)
    error_detalle   TEXT,

    contenido       TEXT,               -- el mensaje crudo, para reprocesar

    -- Para medir latencia de extremo a extremo (metrica del RF3)
    recibido_en     TIMESTAMP NOT NULL DEFAULT now(),
    entregado_en    TIMESTAMP,
    actualizado_en  TIMESTAMP NOT NULL DEFAULT now()
);

-- Indice para que el trabajador de reintentos encuentre rapido
-- lo que le toca, sin recorrer toda la tabla.
CREATE INDEX idx_mensaje_pendiente
    ON mensaje_bus (estado, proximo_intento)
    WHERE estado IN ('FALLIDO', 'REINTENTANDO');

CREATE INDEX idx_mensaje_documento ON mensaje_bus (documento_id);


-- ------------------------------------------------------------
--  2. EVENTO_AUDITORIA  -  cadena de hash (RF5)
--
--  Cada evento guarda el hash del anterior. Si alguien modifica
--  una fila vieja, su hash deja de cuadrar con el que guardo el
--  siguiente evento y la cadena se rompe en ese punto exacto.
--  Es el mismo principio de una cadena de bloques, sin necesidad
--  de una blockchain.
-- ------------------------------------------------------------
CREATE TABLE evento_auditoria (
    secuencia       BIGSERIAL PRIMARY KEY,   -- orden total, no se reusa
    ts              TIMESTAMP NOT NULL DEFAULT now(),

    usuario         VARCHAR(50),
    rol             VARCHAR(20),             -- paciente/admisionista/medico/auditor
    accion          VARCHAR(50),             -- CONSULTAR / CREAR / INGESTAR...
    recurso         VARCHAR(50),             -- Patient / Encounter / HistoriaClinica
    documento_id    BIGINT,                  -- paciente afectado
    resultado       VARCHAR(20),             -- PERMITIDO / DENEGADO / ERROR
    detalle         TEXT,

    hash_anterior   VARCHAR(64),             -- hash del evento previo
    hash_actual     VARCHAR(64) NOT NULL     -- SHA-256(contenido + hash_anterior)
);

CREATE INDEX idx_auditoria_documento ON evento_auditoria (documento_id);
CREATE INDEX idx_auditoria_ts        ON evento_auditoria (ts);


-- ------------------------------------------------------------
--  3. REF_TERMINOLOGIA  -  el ConceptMap (RF3)
--
--  Traduce el codigo propio de cada sede al estandar
--  internacional. Sin esto, cada sede llamaria "DM2", "E11" o
--  "diabetes2" a la misma enfermedad y no se podrian comparar
--  historias entre sedes.
-- ------------------------------------------------------------
CREATE TABLE ref_terminologia (
    sistema       VARCHAR(20)  NOT NULL,     -- CIE10 / LOINC
    codigo_local  VARCHAR(120) NOT NULL,     -- como lo nombra la sede
    codigo_std    VARCHAR(20)  NOT NULL,     -- codigo estandar
    descripcion   VARCHAR(200),
    PRIMARY KEY (sistema, codigo_local)
);

-- Diagnosticos -> CIE-10
INSERT INTO ref_terminologia (sistema, codigo_local, codigo_std, descripcion) VALUES
  ('CIE10', 'DM2',       'E11', 'Diabetes mellitus tipo 2'),
  ('CIE10', 'DIABETES2', 'E11', 'Diabetes mellitus tipo 2'),
  ('CIE10', 'HTA',       'I10', 'Hipertension esencial primaria'),
  ('CIE10', 'OBESIDAD',  'E66', 'Obesidad'),
  ('CIE10', 'IAM',       'I21', 'Infarto agudo de miocardio'),
  ('CIE10', 'NEUMONIA',  'J15', 'Neumonia bacteriana no clasificada'),
  ('CIE10', 'MIGRANA',   'G43', 'Migrana'),
  ('CIE10', 'CEFALEA',   'G44', 'Cefalea tensional'),
  ('CIE10', 'EPOC',      'J44', 'Enfermedad pulmonar obstructiva cronica'),
  ('CIE10', 'ESGUINCE',  'S93', 'Esguince de tobillo'),
  ('CIE10', 'HERIDA',    'S61', 'Herida de muneca y mano');

-- Pruebas de laboratorio -> LOINC
INSERT INTO ref_terminologia (sistema, codigo_local, codigo_std, descripcion) VALUES
  ('LOINC', 'GLUCOSA EN SANGRE',       '2339-0',  'Glucosa en sangre'),
  ('LOINC', 'GLUCOSA',                 '2339-0',  'Glucosa en sangre'),
  ('LOINC', 'HEMOGLOBINA GLICOSILADA', '4548-4',  'Hemoglobina A1c'),
  ('LOINC', 'HBA1C',                   '4548-4',  'Hemoglobina A1c'),
  ('LOINC', 'COLESTEROL TOTAL',        '2093-3',  'Colesterol total'),
  ('LOINC', 'TROPONINA I',             '10839-9', 'Troponina I cardiaca'),
  ('LOINC', 'LEUCOCITOS',              '6690-2',  'Leucocitos en sangre'),
  ('LOINC', 'PROTEINA C REACTIVA',     '1988-5',  'Proteina C reactiva'),
  ('LOINC', 'CREATININA',              '2160-0',  'Creatinina en suero');


-- ------------------------------------------------------------
--  4. Vista de METRICAS  -  el RNF de observabilidad
--     La consulta /metrics del HSB lee de aqui.
-- ------------------------------------------------------------
CREATE VIEW v_metricas_bus AS
SELECT
    count(*)                                            AS total,
    count(*) FILTER (WHERE estado = 'ENTREGADO')        AS entregados,
    count(*) FILTER (WHERE estado = 'RECHAZADO')        AS rechazados,
    count(*) FILTER (WHERE estado = 'MUERTO')           AS muertos,
    count(*) FILTER (WHERE estado IN ('FALLIDO','REINTENTANDO')) AS en_reintento,
    count(*) FILTER (WHERE intentos > 0)                AS con_reintentos,
    COALESCE(round(avg(EXTRACT(EPOCH FROM (entregado_en - recibido_en)) * 1000)
             FILTER (WHERE entregado_en IS NOT NULL), 2), 0) AS latencia_media_ms,
    COALESCE(round(100.0 * count(*) FILTER (WHERE estado IN ('RECHAZADO','MUERTO'))
             / NULLIF(count(*), 0), 2), 0)              AS porcentaje_fallidos
FROM mensaje_bus;


-- ------------------------------------------------------------
--  5. USUARIO_SISTEMA  -  autenticacion y rol  (RF5)
--
--  Vive en bus_db y no en los nodos fragmentados: los nodos
--  estan partidos por documento del paciente, y un usuario del
--  sistema (un medico, un auditor) no pertenece a ninguna
--  particion. Si estuviera repartido, iniciar sesion exigiria
--  preguntarle a los tres nodos.
--
--  LA CLAVE NUNCA SE GUARDA. Se guarda PBKDF2-HMAC-SHA256 de la
--  clave con una sal distinta por usuario (ver seguridad.py).
--  Aunque alguien se robe esta tabla, no obtiene las claves.
--
--  documento_id solo tiene valor para el rol 'paciente': dice
--  de quien es la historia que ese usuario puede ver. Para los
--  demas roles va NULL.
--
--  TODOS ESTOS USUARIOS SON SINTETICOS, para la demostracion.
--  Las claves estan escritas aqui a proposito para que el
--  docente pueda entrar; en un despliegue real se cargarian
--  desde .env y nunca estarian en el repositorio.
-- ------------------------------------------------------------
CREATE TABLE usuario_sistema (
    usuario      VARCHAR(50)  PRIMARY KEY,
    rol          VARCHAR(20)  NOT NULL,
    sal          VARCHAR(40)  NOT NULL,
    clave_hash   VARCHAR(128) NOT NULL,
    documento_id BIGINT,
    activo       BOOLEAN NOT NULL DEFAULT true,
    creado_en    TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT rol_valido CHECK (rol IN
        ('paciente','admisionista','medico','auditor','sistema_sede'))
);

INSERT INTO usuario_sistema (usuario, rol, sal, clave_hash, documento_id) VALUES
  -- Paciente Maria Perez Gomez: solo ve SU propia historia
  --   usuario: maria       clave: maria.demo
  ('maria', 'paciente', 'sal-maria-7f3a',
   '64f3ed0f4857b5cf421c329f560faa7166719137801bec566df465d04ca3235d',
   1098765432),

  -- Admisionista: registra y busca, NO lee diagnosticos
  --   usuario: admision1   clave: admision.demo
  ('admision1', 'admisionista', 'sal-admision-2b91',
   'b5adc8ee6cf765433e3aad166b8182fbc48b635fb73dd1625f417b707751a8d1',
   NULL),

  -- Medico Dr. Carlos Gomez: lee la historia clinica completa
  --   usuario: drcarlos    clave: medico.demo
  ('drcarlos', 'medico', 'sal-medico-5d04',
   '52a8725e37a4aa091aae51b930b63371de480c58f6d7ba2c0f421a6106a95ec5',
   NULL),

  -- Auditor: ve la bitacora y la verifica, NO lee historias
  --   usuario: auditor1    clave: auditor.demo
  ('auditor1', 'auditor', 'sal-auditor-9c2e',
   '4ed419fea524c833f3fa99434056ca30ae4474209cde8b54e663f9abf44344a8',
   NULL),

  -- Cuenta de maquina de Mirth / sedes: solo puede INGESTAR
  --   usuario: mirth-sede1 clave: sistema.demo
  ('mirth-sede1', 'sistema_sede', 'sal-mirth-1a6b',
   'e88095b8811ca56acce27e19a8060720740b0c1b0f3b9eb3ce689709a20d5d83',
   NULL);
