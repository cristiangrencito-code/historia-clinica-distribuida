#!/usr/bin/env python3
"""Envia un mensaje HL7 v2 a un listener MLLP y muestra el ACK.

MLLP envuelve cada mensaje entre bytes de control, porque TCP es un chorro
continuo sin fronteras y el receptor necesita saber donde corta cada mensaje:

    <VT> mensaje <FS><CR>
    0x0B  ...    0x1C 0x0D

Uso:  ./enviar-hl7.py mirth/mensaje-adt.hl7 [host] [puerto]
"""
import socket
import sys

VT, FS, CR = b"\x0b", b"\x1c", b"\x0d"

ruta = sys.argv[1] if len(sys.argv) > 1 else "mirth/mensaje-adt.hl7"
host = sys.argv[2] if len(sys.argv) > 2 else "localhost"
port = int(sys.argv[3]) if len(sys.argv) > 3 else 6661

with open(ruta, "rb") as f:
    mensaje = f.read().rstrip(b"\r\n")

print(f"--> enviando {ruta} a {host}:{port}  ({len(mensaje)} bytes)")
print("--- segmentos ---")
for seg in mensaje.split(CR):
    if seg.strip():
        print("   ", seg.decode("utf-8", "replace"))

with socket.create_connection((host, port), timeout=15) as s:
    s.sendall(VT + mensaje + FS + CR)
    s.settimeout(15)
    buf = b""
    try:
        while FS not in buf:
            trozo = s.recv(4096)
            if not trozo:
                break
            buf += trozo
    except socket.timeout:
        print("\n<-- sin ACK (timeout de 15s)")
        sys.exit(2)

ack = buf.strip(VT + FS + CR)
print("\n<-- ACK recibido:")
for seg in ack.split(CR):
    if seg.strip():
        print("   ", seg.decode("utf-8", "replace"))

texto = ack.decode("utf-8", "replace")
if "|AA|" in texto or "|CA|" in texto:
    print("\nRESULTADO: ACEPTADO (AA)")
elif "|AE|" in texto or "|AR|" in texto:
    print("\nRESULTADO: RECHAZADO (AE/AR) -- revisa el canal")
