#!/bin/bash
# Crea las bases auxiliares en el nodo 1, en el primer arranque:
#   fhir_db -> repositorio de HAPI FHIR
#   bus_db  -> tablas del HSB (mensaje_bus, evento_auditoria, ref_terminologia)
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<SQL
    CREATE DATABASE fhir_db;
    CREATE DATABASE bus_db;
SQL
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bus_db -f /docker-entrypoint-initdb.d/bus-schema.sql
echo "bases fhir_db y bus_db creadas"
