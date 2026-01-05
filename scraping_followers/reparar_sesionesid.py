import time
import json
import os
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 1. CONFIGURA TUS CUENTAS AQUÍ ---
# Escribe tus usuarios y contraseñas reales para generar las cookies
CUENTAS_A_REPARAR = [
    {"user": "fabiangoltra44", "pass": "Colon2501$"},
    {"user": "franciflee",     "pass": "v951753456"},
    {"user": "asdassda846",    "pass": "v951753456"},
    {"user": "rojavi31612",    "pass": "v951753456"}
]

# --- RUTA DE SALIDA ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(SCRIPT_DIR, 'cuentas2.json')

def obtener_session_id(account):
    print(f"\n>>> Procesando: {account['user']}...")
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    # Usamos modo visible para que puedas resolver captchas si salen
    
    driver = None
    session_id = None
    
    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        
        # 1. Ir al login
        driver.get("https://www.instagram.com/accounts/login/")
        
        # 2. Llenar formulario (Espera explícita)
        wait = WebDriverWait(driver, 15)
        user_field = wait.until(EC.element_to_be_clickable((By.NAME, "username")))
        pass_field = driver.find_element(By.NAME, "password")
        
        user_field.send_keys(account['user'])
        pass_field.send_keys(account['pass'])
        pass_field.submit()
        
        print("   Esperando login (15 segs)...")
        time.sleep(10) # Tiempo para que procese el login
        
        # 3. Extraer Cookies
        cookies = driver.get_cookies()
        
        for cookie in cookies:
            if cookie['name'] == 'sessionid':
                session_id = cookie['value']
                print(f"   [ÉXITO] SessionID capturado: {session_id[:10]}...")
                break
        
        if not session_id:
            print("   [ERROR] No se generó cookie 'sessionid'. ¿Contraseña mal o Captcha?")
            # Opcional: input("Presiona Enter si resolviste el captcha manualmente...")
            
    except Exception as e:
        print(f"   [FALLO] Selenium error: {e}")
    finally:
        if driver: driver.quit()
        
    return session_id

def main():
    print("--- REPARADOR DE SESIONES (SELENIUM) ---")
    
    cuentas_finales = []
    
    for acc in CUENTAS_A_REPARAR:
        if acc['pass'] == "TU_CONTRASEÑA_AQUI":
            print(f"[SKIP] {acc['user']} -> No configuraste la contraseña en el script.")
            continue
            
        sid = obtener_session_id(acc)
        
        if sid:
            cuentas_finales.append({
                "user": acc['user'],
                "pass": acc['pass'],
                "sessionid": sid
            })
            # Pausa de seguridad entre logins
            time.sleep(random.uniform(5, 10))
    
    # Guardar en JSON
    if cuentas_finales:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(cuentas_finales, f, indent=4)
        
        print("\n" + "="*40)
        print(f"¡LISTO! Se generó 'cuentas.json' con {len(cuentas_finales)} cuentas válidas.")
        print("Ahora puedes ejecutar tu 'proxy_selenium.py' directamente.")
        print("="*40)
    else:
        print("\n[ERROR] No se pudo recuperar ninguna cuenta.")

if __name__ == "__main__":
    main()