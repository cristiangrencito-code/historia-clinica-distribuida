-- ============================================================
--  DATOS SINTETICOS - NODO 2
--  Fragmento: 4.000.000.000 <= documento_id < 7.000.000.000
--  Todos los datos son inventados.
-- ============================================================

INSERT INTO profesional_salud (id_personal_salud, nombre, especialidad) VALUES
  ('44444444-4444-4444-8444-444444444444', 'Dra. Paula Vergara', 'Pediatria'),
  ('55555555-5555-4555-8555-555555555555', 'Dr. Jorge Salcedo',  'Ortopedia');

INSERT INTO usuario (documento_id, tipo_documento, pais_nacionalidad, nombre_completo,
                     fecha_nacimiento, edad, sexo, genero, ocupacion,
                     pais_residencia, municipio_residencia, zona_residencia) VALUES
  (4123456789, 'CC', 'Colombia', 'LAURA MEJIA ORTIZ',
   '1995-09-30', 31, 'F', 'FEMENINO', 'Ingeniera',
   'Colombia', 'Cartagena', 'URBANA'),
  (4987654321, 'CC', 'Venezuela', 'PEDRO RAMIREZ SOTO',
   '1982-06-18', 44, 'M', 'MASCULINO', 'Albanil',
   'Colombia', 'Corozal', 'RURAL');

INSERT INTO atencion (documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
                      entorno_atencion, via_ingreso, causa_atencion,
                      fecha_triage, clasificacion_triage) VALUES
  (4123456789, 'IPS CARTAGENA', '2026-04-20 11:00:00', 'INTRAMURAL',
   'CONSULTA EXTERNA', 'CONSULTA EXTERNA', 'Cefalea tensional',
   '2026-04-20 11:05:00', '5'),
  (4123456789, 'IPS SINCELEJO', '2026-09-14 16:40:00', 'INTRAMURAL',
   'URGENCIAS', 'URGENCIAS', 'Esguince de tobillo derecho',
   '2026-09-14 16:50:00', '3'),
  (4987654321, 'IPS COROZAL', '2026-07-01 07:30:00', 'INTRAMURAL',
   'URGENCIAS', 'URGENCIAS', 'Herida cortante en mano izquierda',
   '2026-07-01 07:35:00', '3');

INSERT INTO diagnostico (atencion_id, tipo_diagnostico_ingreso, diagnostico_ingreso,
                         tipo_diagnostico_egreso, diagnostico_egreso) VALUES
  (1, 'IMPRESION DIAGNOSTICA', 'G44 - Cefalea tensional',
      'CONFIRMADO NUEVO',      'G44 - Cefalea tensional'),
  (2, 'IMPRESION DIAGNOSTICA', 'S93 - Esguince de tobillo',
      'CONFIRMADO NUEVO',      'S93 - Esguince de tobillo'),
  (3, 'IMPRESION DIAGNOSTICA', 'S61 - Herida de muneca y mano',
      'CONFIRMADO NUEVO',      'S61 - Herida de muneca y mano');

INSERT INTO tecnologia_salud (tecnologia_id, atencion_id, descripcion_medicamento,
                              dosis, via_administracion, frecuencia,
                              dias_tratamiento, unidades_aplicadas,
                              id_personal_salud, finalidad_tecnologia) VALUES
  ('bbbbbbbb-0001-4000-8000-000000000001', 2, 'Ibuprofeno 400 mg',
   '400 mg', 'ORAL', 'CADA 8 HORAS', 5, 15,
   '55555555-5555-4555-8555-555555555555', 'Analgesia y antiinflamatorio'),
  ('bbbbbbbb-0002-4000-8000-000000000002', 3, 'Cefalexina 500 mg',
   '500 mg', 'ORAL', 'CADA 6 HORAS', 7, 28,
   '44444444-4444-4444-8444-444444444444', 'Profilaxis antibiotica');

INSERT INTO egreso (atencion_id, fecha_salida, condicion_salida, codigo_prestador,
                    alergias, responsable_egreso) VALUES
  (2, '2026-09-14 19:00:00', 'VIVO', 'IPS-SIN-001',
   'Penicilina', 'Dr. Jorge Salcedo'),
  (3, '2026-07-01 10:15:00', 'VIVO', 'IPS-COR-003',
   'Ninguna conocida', 'Dra. Paula Vergara');
