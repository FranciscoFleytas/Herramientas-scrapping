import time
import os
import json
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

# --- CONFIGURACIÓN ---
TARGET_POST_URL = "https://www.instagram.com/p/CnsoUs9MtIk/?img_index=1" # Un post cualquiera
TEXTO_PRUEBA = "Esta es una prueba de escritura robusta v2 para el SaaS."
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

def load_account():
    if not os.path.exists(CUENTAS_FILE): return None
    try:
        with open(CUENTAS_FILE, 'r') as f:
            data = json.load(f)
            return data[0] if data else None
    except: return None

# ==============================================================================
# LA SOLUCIÓN: LÓGICA DE ESCRITURA BLINDADA
# ==============================================================================
def human_typing_saas_ready(driver, element_xpath, text):
    """
    Versión mejorada de tu human_type_robust.
    Detecta si el elemento muere (Stale) y lo revive en cada letra.
    """
    wait = WebDriverWait(driver, 10)
    
    # 1. Encontrar y Clickar (Foco inicial)
    try:
        element = wait.until(EC.element_to_be_clickable((By.XPATH, element_xpath)))
        driver.execute_script("arguments[0].click();", element)
        time.sleep(0.5)
    except:
        print("   [Typing] No pude hacer click inicial, intentando escribir igual...")

    # 2. Escribir letra por letra con protección de 'StaleElement'
    print(f"   [Typing] Escribiendo: '{text}'")
    
    for char in text:
        try:
            # Intentamos escribir en el elemento actual
            element.send_keys(char)
            time.sleep(random.uniform(0.03, 0.08)) # Velocidad humana
            
        except StaleElementReferenceException:
            # ¡AQUÍ ESTÁ LA MAGIA!
            # Si Instagram refrescó la caja, el 'element' viejo ya no sirve.
            # Lo buscamos de nuevo INMEDIATAMENTE.
            # print("   [Typing] Elemento refrescado, reconectando...") 
            element = wait.until(EC.presence_of_element_located((By.XPATH, element_xpath)))
            element.send_keys(char)
            time.sleep(random.uniform(0.03, 0.08))

def main():
    print("--- INICIANDO PRUEBA DE ESCRITURA ---")
    
    account = load_account()
    if not account:
        print("Error: No se encontró cuentas.json")
        return

    # Usamos versión 142 como corregimos antes
    options = uc.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=es-AR") 
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
    
    try:
        # Login
        driver.get("https://www.instagram.com/")
        time.sleep(2)
        driver.add_cookie({
            'name': 'sessionid',
            'value': account['sessionid'],
            'domain': '.instagram.com',
            'path': '/'
        })
        driver.refresh()
        time.sleep(5)
        
        # Ir al Post
        print(f"Yendo al post: {TARGET_POST_URL}")
        driver.get(TARGET_POST_URL)
        time.sleep(5)
        
        # Selectores Globales (Inglés y Español)
        xpath_area = "//textarea[@aria-label='Agrega un comentario...'] | //textarea[@aria-label='Add a comment…']"
        
        # Probamos la escritura
        human_typing_saas_ready(driver, xpath_area, TEXTO_PRUEBA)
        
        # Enviar (Enter)
        wait = WebDriverWait(driver, 5)
        box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
        box.send_keys(Keys.ENTER)
        
        print("\n--- PRUEBA FINALIZADA ---")
        print("Verifica en el navegador si el texto se escribió completo.")
        time.sleep(10) # Tiempo para que veas el resultado
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()