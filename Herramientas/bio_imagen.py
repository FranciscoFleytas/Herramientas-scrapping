import time
import os
import random
import shutil
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- CONFIGURACIÓN ---
HEADLESS_MODE = False      # False = Ver el navegador
WAIT_AFTER_UPLOAD = 5      # Tiempo espera tras subir foto

# RUTAS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AVATARES_DIR = os.path.join(SCRIPT_DIR, "AVATARES")
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')
BIO_FILE = os.path.join(SCRIPT_DIR, 'bio.txt')  # <--- NUEVO ARCHIVO

# CREDENCIALES PROXY (Asegúrate que sean las correctas)
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_fe5a76d4-zone-isp_proxy1"
PROXY_PASS = "ir29ecqpebov"

# --- UTILIDADES ---

def create_proxy_auth_folder(host, port, user, password, session_id):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 3,
        "name": "Chrome Proxy Auth",
        "permissions": ["proxy", "webRequest", "webRequestAuthProvider", "webRequestBlocking"],
        "host_permissions": ["<all_urls>"],
        "background": {"service_worker": "background.js"}
    }
    """
    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{scheme: "http", host: "{host}", port: parseInt({port})}},
            bypassList: ["localhost"]
        }}
    }};
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
    function callbackFn(details) {{
        return {{ authCredentials: {{ username: "{user}-session-{session_id}", password: "{password}" }} }};
    }}
    chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
    """
    folder_name = os.path.join(SCRIPT_DIR, f'proxy_auth_{session_id}')
    if not os.path.exists(folder_name): os.makedirs(folder_name)
    with open(os.path.join(folder_name, "manifest.json"), 'w') as f: f.write(manifest_json)
    with open(os.path.join(folder_name, "background.js"), 'w') as f: f.write(background_js)
    return folder_name

def load_accounts():
    if not os.path.exists(CUENTAS_FILE): return []
    try:
        with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def get_random_avatar():
    if not os.path.exists(AVATARES_DIR):
        os.makedirs(AVATARES_DIR)
        return None
    files = [f for f in os.listdir(AVATARES_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not files: return None
    return os.path.join(AVATARES_DIR, random.choice(files))

def get_random_bio():
    """Lee bio.txt y devuelve un bloque aleatorio."""
    if not os.path.exists(BIO_FILE):
        print(f"[WARN] No existe {BIO_FILE}. No se cambiará la bio.")
        return None
    
    try:
        with open(BIO_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Separamos por doble salto de línea para respetar los bloques de texto
        # Si tus bios están separadas por una línea vacía, esto funcionará perfecto.
        bios = content.split('\n\n')
        
        # Limpiamos espacios vacíos
        bios = [b.strip() for b in bios if b.strip()]
        
        if not bios:
            return None
            
        return random.choice(bios)
    except Exception as e:
        print(f"[ERROR BIO] {e}")
        return None

def dismiss_popups(driver):
    buttons_text = ["Not Now", "Ahora no", "Cancel", "Cancelar"]
    for txt in buttons_text:
        try:
            xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"
            elements = driver.find_elements(By.XPATH, xpath)
            for btn in elements:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
        except: pass

def update_profile(account):
    image_path = get_random_avatar()
    current_bio = get_random_bio()  # Obtenemos una bio nueva para ESTA cuenta
    
    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- ACTUALIZANDO CUENTA: {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument("--disable-notifications")
    options.add_argument('--lang=en-US')
    
    if HEADLESS_MODE:
        options.add_argument('--headless=new')

    driver = None
    success = False

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        driver.set_window_size(412, 915)

        # 1. Login
        driver.get("https://www.instagram.com/404")
        time.sleep(2)
        driver.add_cookie({
            'name': 'sessionid',
            'value': account['sessionid'],
            'domain': '.instagram.com',
            'path': '/',
            'secure': True,
            'httpOnly': True
        })

        # 2. Editar Perfil
        driver.get("https://www.instagram.com/accounts/edit/")
        time.sleep(5)

        if "login" in driver.current_url:
            print("[ERROR] SessionID inválida.")
            return False

        dismiss_popups(driver)

        # --- SUBIR FOTO ---
        if image_path:
            try:
                print(f"Subiendo foto: {os.path.basename(image_path)}")
                file_input = driver.find_elements(By.XPATH, "//input[@type='file']")
                
                if not file_input:
                    change_btn = driver.find_element(By.XPATH, "//div[@role='button']//img | //button[contains(text(), 'Change')] | //div[contains(text(), 'Cambiar')]")
                    change_btn.click()
                    time.sleep(2)
                    file_input = driver.find_elements(By.XPATH, "//input[@type='file']")
                
                if file_input:
                    file_input[0].send_keys(os.path.abspath(image_path))
                    time.sleep(WAIT_AFTER_UPLOAD)
                    print("[OK] Foto cargada.")
                    success = True
            except Exception as e:
                print(f"[ERROR FOTO] {e}")

        # --- CAMBIAR BIO ---
        if current_bio:
            try:
                print(f"Escribiendo nueva bio:\n---\n{current_bio}\n---")
                bio_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//textarea"))
                )
                
                bio_input.click()
                time.sleep(0.5)
                # Borrar todo
                bio_input.send_keys(Keys.CONTROL + "a")
                bio_input.send_keys(Keys.DELETE)
                time.sleep(0.5)
                
                # Escribir
                bio_input.send_keys(current_bio)
                time.sleep(1)
                
                # Enviar
                submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
                driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
                time.sleep(1)
                submit_btn.click()
                
                print("[OK] Bio guardada.")
                time.sleep(4)
                success = True
                
            except Exception as e:
                print(f"[ERROR BIO] {e}")
        else:
            print("[INFO] No se seleccionó bio (archivo vacío o error).")

    except Exception as e:
        print(f"[ERROR CRÍTICO] {e}")

    finally:
        if driver: driver.quit()
        if os.path.exists(plugin_path): shutil.rmtree(plugin_path)

    return success

def main():
    print("--- GESTOR DE PERFIL (FOTO + BIO RANDOM) ---")
    
    accounts = load_accounts()
    if not accounts:
        print("ERROR: Crea 'cuentas.json'.")
        return

    print(f"Cuentas cargadas: {len(accounts)}")

    for i, acc in enumerate(accounts):
        print(f"\nProcesando cuenta {i+1}/{len(accounts)}...")
        
        ok = update_profile(acc)
        
        if ok:
            print(">> Perfil actualizado.")
        else:
            print(">> Hubo errores.")
        
        print("Esperando 10 segundos...")
        time.sleep(10)

if __name__ == "__main__":
    main()