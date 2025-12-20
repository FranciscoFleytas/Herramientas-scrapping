import time
import json
import os
import random
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# --- CONFIGURACIÓN ---
TARGET_POST_URL = "https://www.instagram.com/p/CUiIk5VLhNn/" # <--- TU LINK AQUÍ

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

def run_debug(account):
    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- DEBUGGEANDO CON: {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument('--lang=es-AR') 
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    driver = None

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        driver.set_window_size(1280, 900) 

        # Login
        driver.get("https://www.instagram.com/404")
        time.sleep(1)
        driver.add_cookie({
            'name': 'sessionid', 
            'value': account['sessionid'], 
            'domain': '.instagram.com', 
            'path': '/', 
            'secure': True, 
            'httpOnly': True
        })

        print(">>> Navegando al post...")
        driver.get(TARGET_POST_URL)
        time.sleep(8) # Damos tiempo extra para cargar todo

        # --- DIAGNÓSTICO ---
        print("\n--- INICIO REPORTE ELEMENTOS ---")
        
        # 1. Buscar TODOS los Textareas
        textareas = driver.find_elements(By.TAG_NAME, "textarea")
        print(f"\n[TEXTAREAS ENCONTRADOS: {len(textareas)}]")
        for i, ta in enumerate(textareas):
            try:
                visible = ta.is_displayed()
                placeholder = ta.get_attribute("placeholder")
                aria = ta.get_attribute("aria-label")
                classes = ta.get_attribute("class")
                print(f"  #{i+1}: Visible={visible} | Placeholder='{placeholder}' | Aria='{aria}'")
            except: print(f"  #{i+1}: Error leyendo atributos")

        # 2. Buscar Botones de Publicar potenciales
        print(f"\n[POSIBLES BOTONES 'PUBLICAR']")
        # Buscamos elementos que contengan texto clave
        keywords = ["Post", "Publicar", "Enviar", "Send"]
        for kw in keywords:
            elems = driver.find_elements(By.XPATH, f"//*[contains(text(), '{kw}')]")
            for el in elems:
                try:
                    if el.is_displayed():
                        print(f"  Texto='{el.text}' | Tag={el.tag_name} | Clases={el.get_attribute('class')}")
                except: pass

        # 3. Guardar Evidencia
        print("\n>>> Guardando evidencia visual...")
        driver.save_screenshot("DEBUG_VISTA.png")
        print("  - Guardado: DEBUG_VISTA.png")
        
        with open("DEBUG_DOM.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("  - Guardado: DEBUG_DOM.html")
        
        print("\n--- FIN DEL REPORTE ---")
        print("Revisa los archivos generados y pégame la salida de la consola.")

    except Exception as e:
        print(f"[ERROR DEBUG] {e}")

    finally:
        if driver:
            try: driver.quit()
            except: pass
        if os.path.exists(plugin_path): shutil.rmtree(plugin_path)

if __name__ == "__main__":
    accounts = load_accounts()
    if accounts:
        run_debug(accounts[0])
    else:
        print("Faltan cuentas.json")