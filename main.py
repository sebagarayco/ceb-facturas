import os
import time
import csv
import re
import shutil
import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
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
# Configuración de Google Sheets
GOOGLE_SPREADSHEET_NAME = os.getenv("GOOGLE_SPREADSHEET_NAME", "Facturas CEB")
GOOGLE_WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "Sheet1")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_SPREADSHEET = os.getenv("GOOGLE_SPREADSHEET", "false").lower() == "true"
GOOGLE_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Crear carpetas si no existen
os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
os.makedirs(CARPETA_SALIDA, exist_ok=True)

def get_google_client():
    """Devuelve el cliente autenticado de Google Sheets."""
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=GOOGLE_SCOPE)
    return gspread.authorize(creds)

def iniciar_sesion():
    """Inicia sesión en la página web y devuelve una instancia del WebDriver."""
    

    opciones = webdriver.ChromeOptions()
    
    # Configura la carpeta de descargas
    prefs = {"download.default_directory": os.path.abspath(CARPETA_DESCARGAS)}
    opciones.add_experimental_option("prefs", prefs)
    
    # Modo headless para ejecución sin interfaz
    opciones.add_argument('--headless')
    opciones.add_argument('--no-sandbox')
    opciones.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=opciones)
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

def enviar_a_google_sheets(datos):
    client = get_google_client()

    ENCABEZADOS = [
        "Archivo", "Periodo", "Emitida el", "Fecha Límite de Pago", "Vencimiento",
        "Consumo KwH", "Consumo Último Año", "Consumo Promedio Diario", "Cargo Fijo", "Valor KwH"
    ]

    try:
        sheet = client.open(GOOGLE_SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(GOOGLE_SPREADSHEET_NAME)
        sheet.share(CEB_USERNAME, perm_type='user', role='writer')

    try:
        worksheet = sheet.worksheet(GOOGLE_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=GOOGLE_WORKSHEET_NAME, rows="100", cols="20")
        worksheet.append_row(ENCABEZADOS)
    else:
        # Si la hoja ya existe, validar los encabezados
        primera_fila = worksheet.row_values(1)
        if primera_fila != ENCABEZADOS:
            if primera_fila:
                worksheet.delete_rows(1)  # Borra la fila si ya hay algo incorrecto
            worksheet.insert_row(ENCABEZADOS, index=1)

    registros = worksheet.get_all_values()
    archivos_existentes = {fila[0] for fila in registros[1:] if fila}

    nuevas_filas = [fila for fila in datos if fila[0] not in archivos_existentes]

    for fila in nuevas_filas:
        worksheet.append_row(fila)

    print(f"📤 {len(nuevas_filas)} fila(s) nuevas enviadas a Google Sheets: {GOOGLE_SPREADSHEET_NAME} -> {GOOGLE_WORKSHEET_NAME}")
    print(f"   📄 Link de la hoja: https://docs.google.com/spreadsheets/d/{sheet.id}")


def descargar_pdfs(driver):
    """Descarga los PDFs si no existen localmente, basándose en el nombre del período."""
    driver.get(CUENTAS_URL)
    time.sleep(3)

    espera = WebDriverWait(driver, 10)

    # Cambiar el dropdown de cantidad de filas a 36 (máximo)
    try:
        selector_filas = espera.until(EC.presence_of_element_located((By.NAME, "form:tblFacturasCuenta_rppDD")))
        opciones = selector_filas.find_elements(By.TAG_NAME, "option")
        for opcion in opciones:
            if opcion.text.strip() == "36":
                opcion.click()
                time.sleep(2)  # Esperar recarga
                break
    except Exception as e:
        print(f"⚠️ No se pudo cambiar la cantidad de filas a 36: {e}")

    cantidad_descargadas = 0
    facturas_descargadas = set()

    while True:
        try:
            tabla = espera.until(EC.presence_of_element_located((By.ID, "form:tblFacturasCuenta_data")))
            filas = tabla.find_elements(By.TAG_NAME, "tr")

            for fila in filas:
                celdas = fila.find_elements(By.TAG_NAME, "td")

                if len(celdas) < 2:
                    continue

                nombre_periodo = celdas[1].text.strip().replace("/", "-")
                if nombre_periodo in facturas_descargadas:
                    continue  # Evitar procesar dos veces si estamos paginando
                facturas_descargadas.add(nombre_periodo)

                nombre_archivo = f"{nombre_periodo}.pdf"
                ruta_archivo = os.path.join(CARPETA_DESCARGAS, nombre_archivo)

                if os.path.exists(ruta_archivo):
                    print(f"⏭️  Ya existe: {nombre_archivo}, saltando descarga.")
                    continue

                try:
                    boton_descarga = fila.find_element(By.TAG_NAME, "button")
                    boton_descarga.click()
                    print(f"⬇️  Descargando: {nombre_archivo}")
                    time.sleep(2)

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

            # Verificar si hay siguiente página
            try:
                boton_siguiente = driver.find_element(By.CLASS_NAME, "ui-paginator-next")
                clases = boton_siguiente.get_attribute("class")

                if "ui-state-disabled" in clases:
                    break  # Última página

                boton_siguiente.click()
                time.sleep(2)  # Esperar recarga

            except Exception:
                print("⚠️ No se pudo encontrar o hacer clic en el botón de siguiente página.")
                break

        except Exception as e:
            print(f"⚠️ Error al procesar la tabla: {e}")
            break

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

def obtener_archivos_en_sheets():
    client = get_google_client()

    try:
        sheet = client.open(GOOGLE_SPREADSHEET_NAME)
        worksheet = sheet.worksheet(GOOGLE_WORKSHEET_NAME)
        registros = worksheet.get_all_values()
        return {fila[0] for fila in registros[1:] if fila}
    except gspread.exceptions.WorksheetNotFound:
        print(f"⚠️  La hoja '{GOOGLE_WORKSHEET_NAME}' no existe en el spreadsheet '{GOOGLE_SPREADSHEET_NAME}'.")
        return set()
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"⚠️  El spreadsheet '{GOOGLE_SPREADSHEET_NAME}' no existe.")
        return set()
    except Exception as e:
        print(f"⚠️  Error al acceder a Google Sheets: {e}")
        return set()

def procesar_pdfs(archivos_pdf):
    """Procesa PDFs solo si no están ya registrados en output.csv o Google Spreadsheet."""

    datos_extraidos = []

    # Definir encabezados estándar
    headers = [
        "Archivo", "Periodo", "Emitida el", "Fecha Límite de Pago", "Vencimiento",
        "Consumo KwH", "Consumo Último Año", "Consumo Promedio Diario", "Cargo Fijo", "Valor KwH"
    ]

    # Obtener archivos ya procesados en output.csv
    archivos_csv = set()
    if os.path.exists(ARCHIVO_CSV):
        with open(ARCHIVO_CSV, "r", encoding="utf-8") as archivo_csv:
            lector = csv.reader(archivo_csv)
            primera_fila = next(lector, None)

            # Validar encabezados
            if primera_fila != headers:
                print("⚠️  Encabezados CSV incorrectos o faltantes. Corrigiendo...")
                registros = list(lector)
                with open(ARCHIVO_CSV, "w", newline="", encoding="utf-8") as archivo_corregido:
                    escritor = csv.writer(archivo_corregido)
                    escritor.writerow(headers)
                    escritor.writerows(registros)
                    archivos_csv = {fila[0] for fila in registros if fila}
            else:
                archivos_csv = {fila[0] for fila in lector if fila}

    # Obtener archivos ya registrados en Google Spreadsheet
    archivos_sheets = set()
    if GOOGLE_SPREADSHEET:
        print("🔍 Consultando archivos ya cargados en Google Spreadsheet...")
        archivos_sheets = obtener_archivos_en_sheets()

    # Procesar PDFs nuevos
    for pdf in archivos_pdf:
        nombre_pdf = os.path.basename(pdf)

        ya_en_csv = nombre_pdf in archivos_csv
        ya_en_sheets = nombre_pdf in archivos_sheets

        if ya_en_csv and (not GOOGLE_SPREADSHEET or ya_en_sheets):
            print(f"ℹ️  Ya procesado: {nombre_pdf}, omitiendo.")
            continue

        if not os.path.exists(pdf):
            print(f"⚠️  Archivo no encontrado (pero ya estaba registrado): {nombre_pdf}, omitiendo.")
            continue

        print(f"📄 Procesando nuevo archivo: {nombre_pdf}")
        nombre_txt = os.path.splitext(nombre_pdf)[0] + ".txt"
        ruta_txt = os.path.join(CARPETA_SALIDA, nombre_txt)

        texto = extract_text_from_pdf(pdf)

        with open(ruta_txt, "w", encoding="utf-8") as archivo_txt:
            archivo_txt.write(texto)

        (
            consumo, fecha_limite_pago, consumo_ultimo_ano, consumo_promedio_diario, 
            valor_kwh, cargo_fijo, emitida_el, periodo, vencimiento
        ) = extraer_campos(texto)

        datos_extraidos.append([
            nombre_pdf, periodo, emitida_el, fecha_limite_pago, vencimiento, consumo, 
            consumo_ultimo_ano, consumo_promedio_diario, cargo_fijo, valor_kwh 
        ])

    if not datos_extraidos:
        print("✅ No hay nuevos archivos para procesar.")
        return

    # Escribir nuevas líneas en el CSV
    archivo_existe = os.path.exists(ARCHIVO_CSV)
    with open(ARCHIVO_CSV, "a", newline="", encoding="utf-8") as archivo_csv:
        escritor = csv.writer(archivo_csv)
        if not archivo_existe:
            escritor.writerow(headers)
        escritor.writerows(datos_extraidos)

    print(f"✅ Se procesaron {len(datos_extraidos)} archivos nuevos. Actualizado {ARCHIVO_CSV}.")

    if GOOGLE_SPREADSHEET:
        enviar_a_google_sheets(datos_extraidos)
    else:
        print("⚠️  Envío a Google Spreadsheet desactivado.")


if __name__ == "__main__":
    driver = iniciar_sesion()
    archivos_pdf = descargar_pdfs(driver)
    driver.quit()
    procesar_pdfs(archivos_pdf)