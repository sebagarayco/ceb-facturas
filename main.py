import os
import time
import csv
import re
import shutil
import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from pdf_extractor import extract_text_from_pdf
from google.oauth2.service_account import Credentials

# Obtener credenciales desde variables de entorno
CEB_USERNAME = os.getenv("CEB_USERNAME")
CEB_PASSWORD = os.getenv("CEB_PASSWORD")

if not CEB_USERNAME or not CEB_PASSWORD:
    raise ValueError("❌ ERROR: Las variables de entorno CEB_USERNAME y CEB_PASSWORD deben estar definidas.")

# Constantes
LOGIN_URL = "https://oficinavirtual.ceb.coop/index.xhtml"
CUENTAS_URL = "https://oficinavirtual.ceb.coop/ov/cuentas.xhtml"
CARPETA_DESCARGAS = os.getenv("CARPETA_DESCARGAS", "downloads")
CARPETA_SALIDA = os.getenv("CARPETA_SALIDA", "outputs")
ARCHIVO_CSV = os.getenv("ARCHIVO_CSV", "output.csv")
GOOGLE_SPREADSHEET = os.getenv("GOOGLE_SPREADSHEET", "false").lower() == "true"

# Crear carpetas si no existen
os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
os.makedirs(CARPETA_SALIDA, exist_ok=True)

def iniciar_sesion():
    """Inicia sesión en la página web y devuelve una instancia del WebDriver."""
    servicio = Service(ChromeDriverManager().install())
    opciones = webdriver.ChromeOptions()
    prefs = {"download.default_directory": os.path.abspath(CARPETA_DESCARGAS)}
    opciones.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=servicio, options=opciones)
    driver.get(LOGIN_URL)

    espera = WebDriverWait(driver, 10)
    campo_usuario = espera.until(EC.presence_of_element_located((By.ID, "form:email")))
    campo_contraseña = espera.until(EC.presence_of_element_located((By.ID, "form:password")))

    campo_usuario.send_keys(CEB_USERNAME)
    campo_contraseña.send_keys(CEB_PASSWORD)

    boton_login = espera.until(EC.element_to_be_clickable((By.ID, "form:loginButton")))
    boton_login.click()

    time.sleep(5)  # Esperar a que el inicio de sesión se complete
    return driver

def enviar_a_google_sheets(datos, spreadsheet_name="Facturas CEB", worksheet_name="Sheet1"):
    """Envía los datos procesados a una hoja de cálculo de Google Sheets."""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)

    # Abrir el spreadsheet
    try:
        sheet = client.open(spreadsheet_name)
        sheet.share('isebedio@gmail.com', perm_type='user', role='reader')
    except gspread.SpreadsheetNotFound:
        sheet = client.create(spreadsheet_name)
        sheet.share(CEB_USERNAME, perm_type='user', role='writer')

    try:
        worksheet = sheet.worksheet(worksheet_name)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=worksheet_name, rows="100", cols="20")

    # Encabezados
    encabezados = [
        "Archivo", "Periodo", "Emitida el", "Fecha Límite de Pago", "Vencimiento",
        "Consumo KwH", "Consumo Último Año", "Consumo Promedio Diario", "Cargo Fijo", "Valor KwH"
    ]
    
    worksheet.append_row(encabezados)
    for fila in datos:
        worksheet.append_row(fila)

    print(f"📤 Datos enviados a Google Sheets: {spreadsheet_name} -> {worksheet_name}")
    print(f"   📄 Link de la hoja: https://docs.google.com/spreadsheets/d/{sheet.id}")

def descargar_pdfs(driver):
    """Descarga los PDFs si no existen localmente, basándose en el nombre del período."""
    driver.get(CUENTAS_URL)
    time.sleep(3)

    espera = WebDriverWait(driver, 10)
    cantidad_descargadas = 0

    # Esperar a que la tabla esté presente
    tabla = espera.until(EC.presence_of_element_located((By.ID, "form:tblFacturasCuenta_data")))
    filas = tabla.find_elements(By.TAG_NAME, "tr")

    for index, fila in enumerate(filas):
        celdas = fila.find_elements(By.TAG_NAME, "td")

        if len(celdas) < 2:
            continue  # Saltar filas con celdas inesperadas

        nombre_periodo = celdas[1].text.strip().replace("/", "-")
        nombre_archivo = f"{nombre_periodo}.pdf"
        ruta_archivo = os.path.join(CARPETA_DESCARGAS, nombre_archivo)

        if os.path.exists(ruta_archivo):
            print(f"⏭️  Ya existe: {nombre_archivo}, saltando descarga.")
            continue

        try:
            # El botón de descarga está en la última celda (o posición fija)
            boton_descarga = fila.find_element(By.TAG_NAME, "button")
            boton_descarga.click()
            print(f"⬇️  Descargando: {nombre_archivo}")

            # Esperar un momento para que el navegador descargue
            time.sleep(2)

            # Buscar el archivo más reciente descargado
            archivos_pdf = [f for f in os.listdir(CARPETA_DESCARGAS) if f.endswith(".pdf")]
            if archivos_pdf:
                ultimo_archivo = max(
                    [os.path.join(CARPETA_DESCARGAS, f) for f in archivos_pdf],
                    key=os.path.getctime
                )
                shutil.move(ultimo_archivo, ruta_archivo)
                cantidad_descargadas += 1

        except Exception as e:
            print(f"⚠️ Error al intentar descargar para {nombre_periodo}: {e}")
            continue

    print(f"✅ Finalizado. Se descargaron {cantidad_descargadas} archivos nuevos.")
    return [
        os.path.join(CARPETA_DESCARGAS, f) for f in os.listdir(CARPETA_DESCARGAS) if f.endswith(".pdf")
    ]

def extraer_campos(texto):
    """Extrae los valores de los campos requeridos desde el texto."""
    consumo = None
    fecha_limite_pago = None
    consumo_ultimo_ano = None
    consumo_promedio_diario = None
    valor_kwh = None
    cargo_fijo = None
    emitida_el = None
    periodo = None
    vencimiento = None

    # Extraer "Consumo"
    match_consumo = re.search(r"TARIFA:T1R1 M CONSUMO:\s*(\d+)", texto)
    if match_consumo:
        consumo = match_consumo.group(1)

    # Extraer "Fecha límite de pago"
    match_fecha = re.search(r"-- Fecha límite para pago en Entidades:\s*([^.]+)", texto)
    if match_fecha:
        fecha_limite_pago = match_fecha.group(1).strip()

    # Extraer "Consumo Último Año"
    match_consumo_ano = re.search(r"Consumo Promedio Último Año:\s*(\d+)", texto)
    if match_consumo_ano:
        consumo_ultimo_ano = match_consumo_ano.group(1)

    # Extraer "Consumo Promedio Diario"
    match_consumo_diario = re.search(r"Consumo Promedio Diario:\s*(\d+)", texto)
    if match_consumo_diario:
        consumo_promedio_diario = match_consumo_diario.group(1)

    # Extraer "Valor KwH"
    match_valor_kwh = re.search(r"CARGO FIJO=Precio Unitario Facturado Cargo Fijo\s*([\d,.]+)", texto)
    if match_valor_kwh:
        valor_kwh = match_valor_kwh.group(1).replace(",", ".")

    # Extraer "Cargo Fijo" (último valor en la línea que empieza con "Cargo Fijo ")
    match_cargo_fijo = re.search(r"^Cargo Fijo .*?([\d,.]+)\s*$", texto, re.MULTILINE)
    if match_cargo_fijo:
        cargo_fijo = match_cargo_fijo.group(1).replace(",", ".")

    # Extraer "Emitida el", "Periodo" y "Vencimiento"
    match_fechas = re.search(r"(\d{2}/\d{2}/\d{4})\s+([A-ZÁÉÍÓÚÑ]+\s+\d{4})\s+(\d{2}/\d{2}/\d{4})", texto)
    if match_fechas:
        emitida_el = match_fechas.group(1)
        periodo = match_fechas.group(2)
        vencimiento = match_fechas.group(3)

    return (
        consumo, fecha_limite_pago, consumo_ultimo_ano, consumo_promedio_diario, 
        valor_kwh, cargo_fijo, emitida_el, periodo, vencimiento
    )

def procesar_pdfs(archivos_pdf):
    """Procesa los PDFs, guarda el texto extraído en .txt y escribe los datos seleccionados en CSV."""
    datos_extraidos = []

    for pdf in archivos_pdf:
        if os.path.exists(pdf):
            nombre_pdf = os.path.basename(pdf)
            nombre_txt = os.path.splitext(nombre_pdf)[0] + ".txt"
            ruta_txt = os.path.join(CARPETA_SALIDA, nombre_txt)

            # Extraer texto del PDF
            texto = extract_text_from_pdf(pdf)

            # Guardar texto extraído en archivo .txt
            with open(ruta_txt, "w", encoding="utf-8") as archivo_txt:
                archivo_txt.write(texto)

            # Extraer campos específicos
            (
                consumo, fecha_limite_pago, consumo_ultimo_ano, consumo_promedio_diario, 
                valor_kwh, cargo_fijo, emitida_el, periodo, vencimiento
            ) = extraer_campos(texto)

            datos_extraidos.append([
                nombre_pdf, periodo, emitida_el, fecha_limite_pago, vencimiento, consumo, 
                consumo_ultimo_ano, consumo_promedio_diario, cargo_fijo, valor_kwh 
            ])
        else:
            print(f"⚠️ Archivo no encontrado, omitiendo: {pdf}")

    # Guardar datos extraídos en CSV
    with open(ARCHIVO_CSV, "w", newline="", encoding="utf-8") as archivo_csv:
        escritor = csv.writer(archivo_csv)
        escritor.writerow([
            "Archivo", "Periodo", "Emitida el", "Fecha Límite de Pago", "Vencimiento",
            "Consumo KwH", "Consumo Último Año", "Consumo Promedio Diario", "Cargo Fijo", "Valor KwH"
        ])
        escritor.writerows(datos_extraidos)

    print(f"✅ Se procesaron {len(archivos_pdf)} PDFs. Datos guardados en {ARCHIVO_CSV}.")

    # Enviar a Google Sheets
    if GOOGLE_SPREADSHEET:
        print("📊 Enviando datos a Google Sheets...")
        enviar_a_google_sheets(datos_extraidos)
    else:
        print("⚠️  Envío a Google Spreadsheet desactivado. Para activarlo, setear GOOGLE_SPREADSHEET='true' en las variables de entorno.")        

if __name__ == "__main__":
    driver = iniciar_sesion()
    archivos_pdf = descargar_pdfs(driver)
    driver.quit()
    procesar_pdfs(archivos_pdf)