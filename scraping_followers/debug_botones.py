import time
import os
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# --- CONFIGURACIÓN ---
TARGET_POST_URL = "https://www.instagram.com/p/DEp92mTRRjZ/" 
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

def load_account():
    if not os.path.exists(CUENTAS_FILE): return None
    try:
        with open(CUENTAS_FILE, 'r') as f:
            data = json.load(f)
            return data[0] if data else None
    except: return None

def main():
    print("--- INICIANDO DIAGNÓSTICO DE BOTONES (FIX v142) ---")
    
    account = load_account()
    if not account:
        print("Error: No se encontró cuentas.json")
        return

    options = uc.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=es-AR") 
    
    # --- CORRECCIÓN AQUÍ: Forzamos la versión 142 para que coincida con tu navegador ---
    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
    except Exception as e:
        print(f"Error al iniciar Chrome: {e}")
        return
    
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
        driver.get(TARGET_POST_URL)
        time.sleep(5)
        
        print(f"\nANÁLISIS DE: {TARGET_POST_URL}")
        print("="*40)
        
        # 1. Buscar TODOS los SVGs (Iconos)
        # Usamos un selector amplio para ver todo
        svgs = driver.find_elements(By.XPATH, "//*[local-name()='svg']")
        print(f"Total SVGs encontrados en DOM: {len(svgs)}")
        
        found_count = 0
        for i, svg in enumerate(svgs):
            if not svg.is_displayed(): continue
            
            # Obtener Label del SVG o de su padre
            label = svg.get_attribute("aria-label")
            if not label:
                try: label = svg.find_element(By.XPATH, "./..").get_attribute("aria-label")
                except: pass
            
            # Obtener Clase
            clase = svg.get_attribute("class")
            
            # Filtrar iconos muy pequeños
            size = svg.size
            if size['width'] > 10 and size['height'] > 10:
                print(f"[Icono {i}] Label: '{label}' | Class: '{clase}'")
                if label: found_count += 1
                
        print("="*40)
        print(f"Iconos con etiqueta encontrados: {found_count}")
        print("Busca arriba los que digan 'Me gusta' o 'Like' y copia la salida.")
        
        input("\nPresiona ENTER para cerrar...")
        
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

