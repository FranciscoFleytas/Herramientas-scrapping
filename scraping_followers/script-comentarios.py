import time
import json
import os
import random
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- CONFIGURACIÓN ---
TARGET_POST_URL = "https://www.instagram.com/p/CUiIk5VLhNn/" # <--- PEGA TU LINK AQUÍ
TIME_BETWEEN_ACCOUNTS = (60, 120) 

COMMENTS_LIST = [
    "Gran aporte! 👏",
    "Te escribí al DM",
    "Me interesa la info",
    "Excelente post",
    "Check DM please",
    "Totalmente de acuerdo",
    "Info por favor"
]

# PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# RUTAS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

def create_proxy_auth_folder(host, port, user, password, session_id):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 3,
        "name": "Chrome Proxy Auth V3",
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
            data = json.load(f)
            return data if isinstance(data, list) else []
    except: return []

def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.2))

def dismiss_popups(driver):
    buttons = ["Not Now", "Ahora no", "Cancel", "Cancelar"]
    for _ in range(3):
        found = False
        for txt in buttons:
            try:
                xpath = f"//div[@role='dialog']//button[contains(text(), '{txt}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                for btn in elements:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                        found = True
            except: pass
        if not found: break

def execute_comment_task(account, comment_text):
    if not account.get('sessionid'): 
        print(f"[ERROR] {account['user']} sin sessionid.")
        return False

    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- Iniciando: {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument('--lang=es-AR') 
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    driver = None
    success = False

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        driver.set_window_size(1280, 900) 

        # 1. Login y Navegación
        driver.get("https://www.instagram.com/404")
        time.sleep(1)
        driver.add_cookie({
            'name': 'sessionid', 'value': account['sessionid'], 
            'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True
        })

        driver.get(TARGET_POST_URL)
        time.sleep(5)
        dismiss_popups(driver)

        # 2. Interacción con Comentarios
        wait = WebDriverWait(driver, 10)
        print(f"   Buscando caja de comentarios...")

        try:
            # Selector flexible para encontrar el área de texto (textarea o contenteditable)
            comment_box = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//form//textarea | //div[@contenteditable='true'] | //textarea[@aria-label='Agrega un comentario...']")
            ))
            
            # Click para enfocar
            driver.execute_script("arguments[0].click();", comment_box)
            time.sleep(1)
            
            active_element = driver.switch_to.active_element
            
            # Escribir texto
            print(f"   Escribiendo: '{comment_text}'")
            human_type(active_element, comment_text)
            time.sleep(0.5)
            
            # Forzar espacio y borrar para disparar eventos de React (truco de activación)
            active_element.send_keys(" ")
            time.sleep(0.1)
            active_element.send_keys(Keys.BACKSPACE)
            time.sleep(2) # Esperar a que el botón se habilite visualmente

            # 3. Intentar Publicar (Estrategia Doble)
            posted = False
            
            # Opción A: Buscar botón por atributo 'role' y texto contenido (más robusto)
            print("   Buscando botón Publicar...")
            try:
                # Busca cualquier elemento con rol de botón que contenga "Publicar" o "Post"
                post_btn = driver.find_element(By.XPATH, "//div[@role='button'][contains(., 'Publicar')] | //button[contains(., 'Publicar')]")
                
                if post_btn.is_displayed():
                    driver.execute_script("arguments[0].click();", post_btn)
                    posted = True
                    print("   Click realizado en botón.")
            except:
                print("   Botón no encontrado, intentando ENTER...")
            
            # Opción B: Si el botón falla, enviar ENTER
            if not posted:
                active_element.send_keys(Keys.ENTER)
                print("   Enviado tecla ENTER.")
            
            time.sleep(4)

            # 4. Verificación
            # Si el texto ha desaparecido de la caja, se envió correctamente
            try:
                current_text = active_element.get_attribute("value") or active_element.text
                if not current_text or current_text.strip() == "":
                    print("   [EXITO] Comentario publicado.")
                    success = True
                else:
                    print("   [FALLO] El texto sigue en la caja.")
            except:
                # Si el elemento ya no existe (DOM refresh), asumimos éxito
                success = True

        except Exception as e:
            print(f"   [ERROR ELEMENTOS] {e}")

    except Exception as e:
        print(f"   [CRASH GENERAL] {e}")

    finally:
        if driver:
            try: driver.quit()
            except: pass
        if os.path.exists(plugin_path): shutil.rmtree(plugin_path)
    
    return success

def main():
    print("--- BOT COMENTARIOS (FIX SELECTOR EXACTO) ---")
    
    accounts = load_accounts()
    if not accounts:
        print("Faltan cuentas.")
        return

    print(f"Objetivo: {TARGET_POST_URL}")
    random.shuffle(accounts)

    for i, acc in enumerate(accounts):
        txt = random.choice(COMMENTS_LIST)
        res = execute_comment_task(acc, txt)
        
        if res and i < len(accounts) - 1:
            wt = random.randint(TIME_BETWEEN_ACCOUNTS[0], TIME_BETWEEN_ACCOUNTS[1])
            print(f"   [ESPERA] {wt} seg...")
            time.sleep(wt)
        else:
            time.sleep(5)

if __name__ == "__main__":
    main()