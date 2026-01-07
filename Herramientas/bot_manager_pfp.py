import time
import os
import random
import shutil
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACIÓN ---
HEADLESS_MODE = False      # False = Ver el navegador (Recomendado para verificar subidas)
WAIT_AFTER_UPLOAD = 10     # Tiempo para asegurar que Instagram procese la foto

# CARPETA DE FOTOS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AVATARES_DIR = os.path.join(SCRIPT_DIR, "AVATARES")
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

# CREDENCIALES PROXY
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
    """Selecciona una imagen al azar de la carpeta AVATARES."""
    if not os.path.exists(AVATARES_DIR):
        os.makedirs(AVATARES_DIR)
        return None
    
    files = [f for f in os.listdir(AVATARES_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not files: return None
    
    return os.path.join(AVATARES_DIR, random.choice(files))

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

def update_profile_picture(account):
    image_path = get_random_avatar()
    if not image_path:
        print("[ERROR] No hay imágenes en la carpeta 'AVATARES'. Agrega fotos .jpg")
        return False

    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- ACTUALIZANDO FOTO: {account['user']} ---")
    print(f"Imagen seleccionada: {os.path.basename(image_path)}")

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
        driver.set_window_size(412, 915) # Tamaño móvil

        # 1. Inyectar Cookies
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

        # 2. Ir directamente a "Editar Perfil"
        # Esta URL fuerza la versión móvil de edición que tiene el input de archivo accesible
        driver.get("https://www.instagram.com/accounts/edit/")
        time.sleep(5)

        if "login" in driver.current_url:
            print("[ERROR] Cookie vencida o inválida.")
            return False

        dismiss_popups(driver)

        # 3. Subir Foto (Truco Selenium: Enviar ruta al input oculto)
        try:
            # Buscamos el input de tipo file. Instagram suele tenerlo oculto pero presente.
            # A veces hay que hacer click en "Cambiar foto" para que se active el input en el DOM
            
            # Intento A: Buscar input directo
            file_input = driver.find_elements(By.XPATH, "//input[@type='file']")
            
            # Intento B: Si no está, hacer click en el botón azul para generarlo
            if not file_input:
                print("Buscando botón de cambio...")
                change_btn = driver.find_element(By.XPATH, "//div[@role='button']//img | //button[contains(text(), 'Change profile photo')] | //div[contains(text(), 'Cambiar foto')]")
                change_btn.click()
                time.sleep(2)
                file_input = driver.find_elements(By.XPATH, "//input[@type='file']")
            
            if file_input:
                print("Subiendo archivo...")
                # Enviar la ruta ABSOLUTA de la imagen
                file_input[0].send_keys(os.path.abspath(image_path))
                
                # Esperar a que se suba
                print(f"Esperando {WAIT_AFTER_UPLOAD}s para procesar...")
                time.sleep(WAIT_AFTER_UPLOAD)
                
                # Verificar éxito (opcional, buscando mensaje 'Profile photo added')
                print("[OK] Foto enviada.")
                success = True
            else:
                print("[ERROR] No se encontró el campo de subida.")

        except Exception as e:
            print(f"[ERROR SUBIDA] {e}")

    except Exception as e:
        print(f"[ERROR CRITICO] {e}")

    finally:
        if driver: driver.quit()
        if os.path.exists(plugin_path): shutil.rmtree(plugin_path)

    return success

def main():
    print("--- GESTOR DE AVATARES DE INSTAGRAM ---")
    
    accounts = load_accounts()
    if not accounts:
        print("Crea 'cuentas.json' con tus sesiones.")
        return

    if not os.path.exists(AVATARES_DIR) or not os.listdir(AVATARES_DIR):
        print("Crea la carpeta 'AVATARES' y pon fotos .jpg dentro.")
        return

    print(f"Cuentas cargadas: {len(accounts)}")

    for i, acc in enumerate(accounts):
        print(f"\nProcesando cuenta {i+1}/{len(accounts)}...")
        
        ok = update_profile_picture(acc)
        
        if ok:
            print("Cuenta actualizada correctamente.")
        else:
            print("Falló la actualización.")
        
        # Pausa entre cuentas para no saturar el proxy
        print("Esperando 10 segundos antes de la siguiente...")
        time.sleep(10)

if __name__ == "__main__":
    main()