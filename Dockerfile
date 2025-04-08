# Imagen base oficial de Python (versión 3.11) basada en Debian slim
FROM python:3.11-slim

# Instalamos Chrome y sus dependencias
RUN apt-get update && \
    apt-get install -y wget gnupg unzip fonts-liberation libnss3 libxss1 \
    libasound2 libatk-bridge2.0-0 libgtk-3-0 libx11-xcb1 libxcb-dri3-0 \
    libgbm1 libxshmfence1 && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get -fy install && \
    rm google-chrome-stable_current_amd64.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos todos los archivos del proyecto al contenedor
COPY . .

# Instalamos las dependencias de Python listadas en requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Comando por defecto al ejecutar el contenedor (puede ser sobrescrito)
CMD ["python", "main.py"]
