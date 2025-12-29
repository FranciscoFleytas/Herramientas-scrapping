import time
import json
import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACION ---
# Pega aqui el LINK de un post (foto o reel) para probar
TARGET_POST_URL = "https://www.instagram.com/p/DEp92mTRRjZ/" 

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

def load_account():
    if not os.path.exists(CUENTAS_FILE): return None
    with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data[0]

def run_debug():
    account = load_account()
    if not account:
        print("Falta cuentas.json")
        return

    print("--- INICIANDO RASTREO DE CAJA DE COMENTARIOS ---")
    
    options = uc.ChromeOptions()
    # Forzamos español para coincidir con tu captura "Agrega un comentario..."
    options.add_argument("--lang=es-AR") 
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
    driver.set_window_size(1280, 850)

    try:
        # Login
        driver.get("https://www.instagram.com/404")
        time.sleep(2)
        driver.add_cookie({'name': 'sessionid', 'value': account['sessionid'], 'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True})
        
        # Ir al post
        print(f"Visitando: {TARGET_POST_URL}")
        driver.get(TARGET_POST_URL)
        time.sleep(6)
        
        print("\n--- ESCANEANDO ELEMENTOS ---")
        
        # Estrategias de búsqueda (de la más obvia a la más técnica)
        estrategias = [
            "//textarea",  # Casi siempre es un textarea
            "//*[contains(text(), 'Agrega un comentario')]",
            "//*[contains(@aria-label, 'Agrega un comentario')]",
            "//*[contains(@placeholder, 'Agrega un comentario')]",
            "//form//textarea"
        ]
        
        encontrados = []

        for xpath in estrategias:
            try:
                elementos = driver.find_elements(By.XPATH, xpath)
                for el in elementos:
                    if el.is_displayed():
                        # Evitar duplicados en la lista visual
                        if el in encontrados: continue
                        
                        encontrados.append(el)
                        
                        # RESALTAR VISUALMENTE
                        driver.execute_script("arguments[0].style.border='5px solid red'; arguments[0].style.backgroundColor='yellow';", el)
                        
                        print(f"\n✅ ELEMENTO DETECTADO (XPath: {xpath}):")
                        print(f"   TAG: <{el.tag_name}>")
                        print(f"   ARIA-LABEL: {el.get_attribute('aria-label')}")
                        print(f"   PLACEHOLDER: {el.get_attribute('placeholder')}")
                        print(f"   CLASES: {el.get_attribute('class')}")
                        print(f"   HTML PARCIAL: {el.get_attribute('outerHTML')[:200]}...")
                        print("-" * 50)
            except: pass

        if not encontrados:
            print("❌ NO se encontró ninguna caja de texto visible.")
            print("Posible causa: El post tiene comentarios desactivados o el selector cambió.")
        else:
            print(f"\n📸 Mira el navegador. He resaltado {len(encontrados)} elementos en ROJO.")
            
        # Mantener abierto
        time.sleep(60)

    finally:
        driver.quit()

if __name__ == "__main__":
    run_debug()