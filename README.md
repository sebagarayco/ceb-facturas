# Descarga y Extracción de Facturas de la Cooperativa de Electricidad Bariloche

Este script automatiza la descarga de facturas de electricidad desde la Oficina Virtual de la **Cooperativa de Electricidad Bariloche (CEB)** y extrae la información relevante para almacenarla en un archivo CSV y en una hoja de cálculo de Google Sheets.

## Requisitos

1. Tener instalado **Python 3**.
2. Instalar las dependencias necesarias ejecutando:
   ```sh
   pip install -r requirements.txt
   ```
3. Configurar las credenciales en variables de entorno:
   - `CEB_USERNAME`: Correo electrónico asociado a la cuenta de la CEB.
   - `CEB_PASSWORD`: Contraseña de la cuenta de la CEB.

## Uso

1. Asegúrate de haber configurado las variables de entorno:

   En sistemas tipo Unix (Linux/macOS):
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
2. **Descarga todas las facturas** disponibles en formato PDF, omitiendo aquellas que ya existen en la carpeta `downloads/`.
3. **Extrae la información relevante** de cada factura, como:
   - Consumo en kWh.
   - Fecha de vencimiento.
   - Cargo fijo y valor del kWh.
   - Período de facturación.
4. **Guarda los datos en** `output.csv` y también los sube a Google Sheets (por defecto, a una hoja llamada "Datos" dentro del documento "Facturas CEB").

## Directorios y Archivos

- `downloads/` → Carpeta donde se almacenan los PDFs descargados.
- `outputs/` → Carpeta donde se guardan los archivos de texto extraídos.
- `output.csv` → Archivo final con los datos extraídos de las facturas.

## Notas

- Si las credenciales no están configuradas correctamente en las variables de entorno, el script arrojará un error y se detendrá.
- Se recomienda limpiar la carpeta `downloads/` antes de ejecutar el script si deseas forzar la descarga de todos los archivos nuevamente.

## Dependencias

Este script utiliza:

- `selenium` para automatizar la navegación web.
- `webdriver-manager` para gestionar el controlador de Chrome.
- `PyMuPDF` (`fitz`) para extraer texto de los archivos PDF.
- `gspread` y `google-auth` para interactuar con Google Sheets.

## Cómo crear las credenciales para Google Sheets

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un nuevo proyecto o selecciona uno existente.
3. Habilita la **Google Sheets API**:
   - Ve a **APIs y servicios > Biblioteca**.
   - Busca **Google Sheets API** y haz clic en "Habilitar".
4. Crea una cuenta de servicio:
   - Ve a **APIs y servicios > Credenciales**.
   - Haz clic en **Crear credencial > Cuenta de servicio**.
   - Asigna un nombre y descripción.
   - En el paso de "permisos", puedes omitirlo.
   - Una vez creada, haz clic en la cuenta de servicio y luego en **Claves** > **Agregar clave** > **JSON**.
   - Se descargará un archivo `.json` que deberás mover a una ubicación segura.
5. Comparte el Google Spreadsheet con el correo de la cuenta de servicio (ej. `nombre-cuenta@nombre-proyecto.iam.gserviceaccount.com`) con permisos de **Editor**.
6. Usa la ruta del archivo `.json` descargado en la variable de entorno `GOOGLE_SHEETS_CREDENTIALS_JSON`.

## Ejemplo de Salida (`output.csv`)

```csv
Archivo,Periodo,Emitida el,Fecha Límite de Pago,Vencimiento,Consumo,Consumo Último Año,Consumo Promedio Diario,Cargo Fijo,Valor KwH
ENE 2024.pdf,Enero 2024,01/01/2024,10/01/2024,15/01/2024,350,4200,11.5,500.00,12.34
FEB 2024.pdf,Febrero 2024,01/02/2024,10/02/2024,15/02/2024,360,4300,12.0,505.00,12.50
```
