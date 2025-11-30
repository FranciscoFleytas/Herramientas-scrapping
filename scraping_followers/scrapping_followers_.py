import time
import random
import os
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACIÓN ---
TARGET_PROFILE = "rkcoaching__"

# RUTA ACTUAL DEL SCRIPT
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Directorio para guardar CSVs
CSV_FILENAME = os.path.join(SCRIPT_DIR, f'scraped_{TARGET_PROFILE}.csv')

def run_scraper_linux():
    print("--- INICIANDO EN LINUX MINT ---")
    
    options = uc.ChromeOptions()
    options.add_argument('--lang=es-AR')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage') # Vital para Linux (evita crash por memoria compartida)
    
    # NO definas binary_location si instalaste Chrome con apt (Paso 1).
    # UC lo encontrará en /usr/bin/google-chrome automáticamente.

    try:
        # Iniciar driver
        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.set_window_size(412, 915) # Tamaño móvil

        # Prueba de navegación
        driver.get("https://www.instagram.com/")
        print("Navegador abierto correctamente.")
        
        time.sleep(5)
        # ... Aquí iría el resto de tu lógica de login/scraping ...

    except Exception as e:
        print(f"Error: {e}")
    finally:
        try: driver.quit()
        except: pass

if __name__ == "__main__":
    run_scraper_linux()