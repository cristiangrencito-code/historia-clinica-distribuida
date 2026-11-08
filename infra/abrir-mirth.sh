#!/usr/bin/env bash
# Mirth Connect Administrator 4.5.2 sin Java Web Start.
#
# Contexto (por que hace falta todo esto):
#  1. Mirth sirve el Administrator por Java Web Start, eliminado en Java 11+.
#     Los JAR del cliente se sacan del propio contenedor:
#       docker cp mirth:/opt/connect/client-lib  ./mirth-admin-lib
#       docker cp mirth:/opt/connect/extensions  ./mirth-extensions
#  2. El openjfx.jar de Mirth es de 2018 y no trae librerias nativas: en Java 8
#     el JRE ya incluia JavaFX, en Java 11+ no. Usamos el OpenJFX del sistema
#     (paquete openjfx) y el jar viejo queda en mirth-admin-lib/_deshabilitado/.
#  3. Las extensiones van en el classpath aparte: ahi viven los conectores
#     (TCP Listener, HTTP Sender) y los tipos de dato (HL7 v2.x, JSON).
cd "$(dirname "$0")" || exit 1

JFX_LIB=/usr/share/openjfx/lib
if [ ! -d "$JFX_LIB" ]; then
  echo "ERROR: falta OpenJFX. Instalalo con:  sudo apt-get install -y openjfx" >&2
  exit 1
fi
if [ ! -d mirth-extensions ]; then
  echo "ERROR: falta mirth-extensions/. Recuperalo con:" >&2
  echo "  docker cp mirth:/opt/connect/extensions ./mirth-extensions" >&2
  exit 1
fi

# classpath: el ORDEN importa.
#   mirth-client.jar trae una copia PARCHEADA de RSyntaxTextArea con un
#   constructor extra, InsertBreakAction(String), que el codigo de Mirth llama.
#   mirth-admin-lib/ tambien incluye rsyntaxtextarea-2.5.6.jar, la version
#   original, que NO lo tiene. Con el comodin "dir/*" el orden lo decide el
#   sistema de archivos; si gana la original -> NoSuchMethodError al abrir
#   cualquier editor de codigo. Por eso mirth-client.jar va primero y explicito.
#   (El comodin de Java solo expande un nivel, de ahi el bucle de extensiones.)
CP="mirth-admin-lib/mirth-client.jar"
CP="$CP:mirth-admin-lib/*"
for d in mirth-extensions/*/; do CP="$CP:${d}*"; done

java \
  -Xmx512m \
  --module-path "$JFX_LIB" \
  -Djava.library.path=/usr/lib/x86_64-linux-gnu/jni \
  --add-modules=javafx.controls,javafx.swing,javafx.web,javafx.media \
  --add-modules=java.sql.rowset \
  --add-exports=java.base/com.sun.crypto.provider=ALL-UNNAMED \
  --add-exports=java.base/sun.security.provider=ALL-UNNAMED \
  --add-exports=java.base/sun.security.action=ALL-UNNAMED \
  --add-opens=java.base/java.lang=ALL-UNNAMED \
  --add-opens=java.base/java.lang.reflect=ALL-UNNAMED \
  --add-opens=java.base/java.math=ALL-UNNAMED \
  --add-opens=java.base/java.net=ALL-UNNAMED \
  --add-opens=java.base/java.security=ALL-UNNAMED \
  --add-opens=java.base/java.security.cert=ALL-UNNAMED \
  --add-opens=java.base/java.text=ALL-UNNAMED \
  --add-opens=java.base/java.util=ALL-UNNAMED \
  --add-opens=java.base/sun.security.pkcs=ALL-UNNAMED \
  --add-opens=java.base/sun.security.rsa=ALL-UNNAMED \
  --add-opens=java.base/sun.security.x509=ALL-UNNAMED \
  --add-opens=java.desktop/java.awt=ALL-UNNAMED \
  --add-opens=java.desktop/java.awt.color=ALL-UNNAMED \
  --add-opens=java.desktop/java.awt.font=ALL-UNNAMED \
  --add-opens=java.desktop/javax.swing=ALL-UNNAMED \
  --add-opens=java.xml/com.sun.org.apache.xalan.internal.xsltc.trax=ALL-UNNAMED \
  -cp "$CP" \
  com.mirth.connect.client.ui.Mirth
