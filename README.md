# Descarga y Extracción de Facturas de la Cooperativa de Electricidad Bariloche

Este script automatiza la descarga de facturas de electricidad desde la Oficina Virtual de la **Cooperativa de Electricidad Bariloche (CEB)** y extrae la información relevante para almacenarla en un archivo CSV.

## Requisitos

1. Tener instalado **Python 3**.
2. Instalar las dependencias necesarias ejecutando:
   ```sh
   pip install -r requirements.txt
   ```
3. Configurar las credenciales de usuario en variables de entorno:
   - `CEB_USERNAME`: Correo electrónico asociado a la cuenta de la CEB.
   - `CEB_PASSWORD`: Contraseña de la cuenta de la CEB.

## Uso

1. Asegúrate de haber configurado las variables de entorno:

   ```sh
   export CEB_USERNAME="tu_email@example.com"
   export CEB_PASSWORD="tu_contraseña"
   ```

   En Windows (PowerShell):

   ```powershell
   $env:CEB_USERNAME="tu_email@example.com"
   $env:CEB_PASSWORD="tu_contraseña"
   ```

2. Ejecuta el script:

   ```sh
   python main.py
   ```

## Funcionamiento

1. **Inicia sesión** en la Oficina Virtual de la CEB usando Selenium.
2. **Descarga todas las facturas** disponibles en formato PDF.
3. **Extrae la información relevante**, como:
   - Consumo en kWh.
   - Fecha de vencimiento.
   - Cargo fijo y valor del kWh.
   - Período de facturación.
4. **Guarda los datos en** `output.csv`, con el siguiente formato:

   ```csv
   Archivo,Periodo,Emitida el,Fecha Límite de Pago,Vencimiento,Consumo,Consumo Último Año,Consumo Promedio Diario,Cargo Fijo,Valor KwH
   factura_1.pdf,Enero 2024,01/01/2024,10/01/2024,15/01/2024,350,4200,11.5,500.00,12.34
   ```

## Directorios y Archivos

- `downloads/` → Carpeta donde se almacenan los PDFs descargados.
- `outputs/` → Carpeta donde se guardan los archivos de texto extraídos.
- `output.csv` → Archivo final con los datos extraídos de las facturas.

## Notas

- Si las credenciales no están configuradas en las variables de entorno, el script arrojará un error y se detendrá.
- Se recomienda limpiar la carpeta `downloads/` antes de ejecutar el script para evitar archivos antiguos.

## Dependencias

Este script utiliza:

- `selenium` para automatizar la navegación web.
- `webdriver-manager` para gestionar el controlador de Chrome.
- `pdf_extractor` para extraer texto de los archivos PDF.
