-- ============================================================
--  DATOS SINTETICOS - NODO 3
--  Fragmento: documento_id >= 7.000.000.000
--  Todos los datos son inventados.
-- ============================================================

INSERT INTO profesional_salud (id_personal_salud, nombre, especialidad) VALUES
  ('66666666-6666-4666-8666-666666666666', 'Dra. Sofia Barros',   'Medicina General'),
  ('77777777-7777-4777-8777-777777777777', 'Dr. Ricardo Pineda',  'Neumologia');

INSERT INTO usuario (documento_id, tipo_documento, pais_nacionalidad, nombre_completo,
                     fecha_nacimiento, edad, sexo, genero, ocupacion,
                     pais_residencia, municipio_residencia, zona_residencia) VALUES
  (7123456789, 'CC', 'Colombia', 'JUAN MARTINEZ CANO',
   '1970-01-25', 56, 'M', 'MASCULINO', 'Agricultor',
   'Colombia', 'Corozal', 'RURAL'),
  (7987654321, 'CC', 'Colombia', 'ELENA TORRES VEGA',
   '2001-12-03', 24, 'F', 'FEMENINO', 'Estudiante',
   'Colombia', 'Sincelejo', 'URBANA');

INSERT INTO atencion (documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
                      entorno_atencion, via_ingreso, causa_atencion,
                      fecha_triage, clasificacion_triage) VALUES
  (7123456789, 'IPS COROZAL', '2026-02-11 08:00:00', 'INTRAMURAL',
   'URGENCIAS', 'URGENCIAS', 'Disnea de esfuerzo progresiva',
   '2026-02-11 08:10:00', '2'),
  (7123456789, 'IPS CARTAGENA', '2026-06-22 09:15:00', 'INTRAMURAL',
   'CONSULTA EXTERNA', 'CONSULTA EXTERNA', 'Control de EPOC',
   '2026-06-22 09:20:00', '4'),
  (7987654321, 'IPS SINCELEJO', '2026-10-05 13:00:00', 'INTRAMURAL',
   'CONSULTA EXTERNA', 'CONSULTA EXTERNA', 'Control de anticoncepcion',
   '2026-10-05 13:05:00', '5');

INSERT INTO diagnostico (atencion_id, tipo_diagnostico_ingreso, diagnostico_ingreso,
                         tipo_diagnostico_egreso, diagnostico_egreso) VALUES
  (1, 'IMPRESION DIAGNOSTICA', 'J44 - EPOC',
      'CONFIRMADO NUEVO',      'J44 - EPOC'),
  (2, 'CONFIRMADO REPETIDO',   'J44 - EPOC',
      'CONFIRMADO REPETIDO',   'J44 - EPOC'),
  (3, 'IMPRESION DIAGNOSTICA', 'Z30 - Atencion para anticoncepcion',
      'CONFIRMADO NUEVO',      'Z30 - Atencion para anticoncepcion');

INSERT INTO tecnologia_salud (tecnologia_id, atencion_id, descripcion_medicamento,
                              dosis, via_administracion, frecuencia,
                              dias_tratamiento, unidades_aplicadas,
                              id_personal_salud, finalidad_tecnologia) VALUES
  ('cccccccc-0001-4000-8000-000000000001', 1, 'Salbutamol inhalador',
   '100 mcg', 'INHALATORIA', 'CADA 6 HORAS', 30, 120,
   '77777777-7777-4777-8777-777777777777', 'Broncodilatacion');

INSERT INTO egreso (atencion_id, fecha_salida, condicion_salida, codigo_prestador,
                    alergias, antecedente_familiar, responsable_egreso) VALUES
  (1, '2026-02-13 12:00:00', 'VIVO', 'IPS-COR-003',
   'Ninguna conocida', 'Padre con EPOC', 'Dr. Ricardo Pineda');
