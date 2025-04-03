import time
import os
from selenium.webdriver.common.by import By

def download_pdfs(driver, download_folder):
    ver_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Ver')]")
    pdf_files = []

    for button in ver_buttons:
        button.click()
        time.sleep(3)  # Wait for download
        
        # Get the last downloaded file
        downloaded_files = sorted(os.listdir(download_folder), key=lambda x: os.path.getmtime(os.path.join(download_folder, x)), reverse=True)
        if downloaded_files:
            latest_file = os.path.join(download_folder, downloaded_files[0])
            pdf_files.append(latest_file)

    return pdf_files

