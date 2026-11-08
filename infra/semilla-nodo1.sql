-- ============================================================
--  DATOS SINTETICOS - NODO 1  (documento_id < 4.000.000.000)
--
--  REGLA DEL PARCIAL: "Solo datos sinteticos. Ningun dato real
--  de pacientes entra al repositorio ni a la demo."
--  Todos los nombres y documentos de aqui son inventados.
--
--  LA PACIENTE DE LA DEMO:
--  Maria Perez Gomez, documento 1098765432, tiene TRES atenciones
--  en TRES sedes distintas (Sincelejo, Cartagena y Corozal).
--
--  Fijate en la distincion:
--    - El NODO lo decide el documento (1098765432 < 4e9 -> nodo1)
--    - La SEDE la dice atencion.entidad_salud
--  Por eso su historia esta fraccionada entre sedes aunque viva
--  fisicamente en un solo nodo. Esa es la consulta unificada que
--  pide el RF4.
-- ============================================================

-- ---------- Profesionales ----------
INSERT INTO profesional_salud (id_personal_salud, nombre, especialidad) VALUES
  ('11111111-1111-4111-8111-111111111111', 'Dr. Carlos Gomez',  'Medicina Interna'),
  ('22222222-2222-4222-8222-222222222222', 'Dra. Ana Restrepo', 'Urgencias'),
  ('33333333-3333-4333-8333-333333333333', 'Dr. Luis Narvaez',  'Cardiologia');

-- ---------- Pacientes ----------
INSERT INTO usuario (documento_id, tipo_documento, pais_nacionalidad, nombre_completo,
                     fecha_nacimiento, edad, sexo, genero, ocupacion,
                     pais_residencia, municipio_residencia, zona_residencia) VALUES
  (1098765432, 'CC', 'Colombia', 'MARIA PEREZ GOMEZ',
   '1985-07-22', 41, 'F', 'FEMENINO', 'Docente',
   'Colombia', 'Sincelejo', 'URBANA'),

  (1033445566, 'CC', 'Colombia', 'ANDRES LOPEZ RUIZ',
   '1990-11-05', 36, 'M', 'MASCULINO', 'Conductor',
   'Colombia', 'Sincelejo', 'URBANA'),

  (1055667788, 'CC', 'Colombia', 'CARLOS DIAZ MORA',
   '1978-02-14', 48, 'M', 'MASCULINO', 'Comerciante',
   'Colombia', 'Cartagena', 'URBANA');

-- ---------- Atenciones de MARIA en las TRES sedes ----------

-- Sede 1: SINCELEJO - urgencias por diabetes descompensada
INSERT INTO atencion (documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
                      entorno_atencion, via_ingreso, causa_atencion,
                      fecha_triage, clasificacion_triage) VALUES
  (1098765432, 'IPS SINCELEJO', '2026-03-10 09:30:00', 'INTRAMURAL',
   'URGENCIAS', 'URGENCIAS', 'Poliuria y perdida de peso de 2 semanas',
   '2026-03-10 09:45:00', '2');

-- Sede 2: CARTAGENA - consulta externa de control
INSERT INTO atencion (documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
                      entorno_atencion, via_ingreso, causa_atencion,
                      fecha_triage, clasificacion_triage) VALUES
  (1098765432, 'IPS CARTAGENA', '2026-05-15 14:20:00', 'INTRAMURAL',
   'CONSULTA EXTERNA', 'CONSULTA EXTERNA', 'Control de peso y perfil lipidico',
   '2026-05-15 14:25:00', '4');

-- Sede 3: COROZAL - urgencias por neumonia
INSERT INTO atencion (documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
                      entorno_atencion, via_ingreso, causa_atencion,
                      fecha_triage, clasificacion_triage) VALUES
  (1098765432, 'IPS COROZAL', '2026-08-02 10:45:00', 'INTRAMURAL',
   'URGENCIAS', 'URGENCIAS', 'Fiebre y tos productiva de 4 dias',
   '2026-08-02 10:55:00', '3');

-- ---------- Atenciones de los otros pacientes ----------
INSERT INTO atencion (documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
                      entorno_atencion, via_ingreso, causa_atencion,
                      fecha_triage, clasificacion_triage) VALUES
  (1033445566, 'IPS SINCELEJO', '2026-03-12 10:15:00', 'INTRAMURAL',
   'CONSULTA EXTERNA', 'CONSULTA EXTERNA', 'Cefalea recurrente',
   '2026-03-12 10:20:00', '5'),
  (1055667788, 'IPS CARTAGENA', '2026-05-18 08:05:00', 'INTRAMURAL',
   'URGENCIAS', 'URGENCIAS', 'Dolor toracico opresivo',
   '2026-05-18 08:10:00', '1');

-- ---------- Diagnosticos (codigos CIE-10) ----------
INSERT INTO diagnostico (atencion_id, tipo_diagnostico_ingreso, diagnostico_ingreso,
                         tipo_diagnostico_egreso, diagnostico_egreso) VALUES
  (1, 'IMPRESION DIAGNOSTICA', 'E11 - Diabetes mellitus tipo 2',
      'CONFIRMADO NUEVO',      'E11 - Diabetes mellitus tipo 2'),
  (2, 'CONFIRMADO REPETIDO',   'E66 - Obesidad',
      'CONFIRMADO REPETIDO',   'E66 - Obesidad'),
  (3, 'IMPRESION DIAGNOSTICA', 'J15 - Neumonia bacteriana',
      'CONFIRMADO NUEVO',      'J15 - Neumonia bacteriana'),
  (4, 'IMPRESION DIAGNOSTICA', 'G43 - Migrana',
      'CONFIRMADO NUEVO',      'G43 - Migrana'),
  (5, 'IMPRESION DIAGNOSTICA', 'I21 - Infarto agudo de miocardio',
      'CONFIRMADO NUEVO',      'I21 - Infarto agudo de miocardio');

-- ---------- Medicamentos ----------
INSERT INTO tecnologia_salud (tecnologia_id, atencion_id, descripcion_medicamento,
                              dosis, via_administracion, frecuencia,
                              dias_tratamiento, unidades_aplicadas,
                              id_personal_salud, finalidad_tecnologia) VALUES
  ('aaaaaaaa-0001-4000-8000-000000000001', 1, 'Metformina 850 mg',
   '850 mg', 'ORAL', 'CADA 12 HORAS', 30, 60,
   '11111111-1111-4111-8111-111111111111', 'Control glucemico'),
  ('aaaaaaaa-0002-4000-8000-000000000002', 3, 'Amoxicilina 500 mg',
   '500 mg', 'ORAL', 'CADA 8 HORAS', 7, 21,
   '22222222-2222-4222-8222-222222222222', 'Tratamiento antibiotico'),
  ('aaaaaaaa-0003-4000-8000-000000000003', 5, 'Acido acetilsalicilico 100 mg',
   '100 mg', 'ORAL', 'CADA 24 HORAS', 90, 90,
   '33333333-3333-4333-8333-333333333333', 'Antiagregacion plaquetaria');

-- ---------- Egresos ----------
INSERT INTO egreso (atencion_id, fecha_salida, condicion_salida, codigo_prestador,
                    alergias, antecedente_familiar, responsable_egreso) VALUES
  (1, '2026-03-10 18:00:00', 'VIVO', 'IPS-SIN-001',
   'Ninguna conocida', 'Madre con diabetes tipo 2', 'Dr. Carlos Gomez'),
  (3, '2026-08-05 11:00:00', 'VIVO', 'IPS-COR-003',
   'Ninguna conocida', 'Madre con diabetes tipo 2', 'Dra. Ana Restrepo');
