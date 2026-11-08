# Imagen del HSB.
#
# OJO con el contexto: se construye desde la RAIZ del proyecto
# (ver docker-compose.yml: context "." y dockerfile "hsb/Dockerfile"),
# no desde esta carpeta. Es para poder copiar seguridad.py, que
# vive en la raiz porque lo comparten el bus y la app: el bus
# emite el token y la app lo valida, y los dos tienen que usar
# exactamente el mismo codigo de firma. Si hubiera dos copias,
# el dia que una cambiara los tokens dejarian de validarse.
FROM python:3.11-slim
WORKDIR /app
COPY hsb/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hsb/normalizador.py hsb/parsers.py hsb/bus.py seguridad.py ./
EXPOSE 8002
CMD ["uvicorn", "bus:app", "--host", "0.0.0.0", "--port", "8002"]
