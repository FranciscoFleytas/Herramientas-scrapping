import time
import json
import csv
import os
import random
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- CONFIGURACIÓN DE VOLUMEN ALTO ---
MAX_DMS_PER_ACCOUNT_DAILY = 45   # Aumentado (Si tu cuenta es antigua)
TIME_BETWEEN_DMS = (120, 300)    # Espera normal entre mensajes (2 a 5 min)

# --- SISTEMA DE RÁFAGAS (ANTI-BOT) ---
BATCH_SIZE = (5, 8)              # Enviar entre 5 y 8 mensajes seguidos...
LONG_PAUSE_TIME = (900, 1800)    # ...y luego descansar 15-30 minutos (simula vida real)

INPUT_CSV = "leads_para_enviar.csv"

# --- SPINTAX ---
PART_A = ["Hola", "Buenas", "Hey", "Qué tal", "Hola qué tal"]
PART_B = ["vi tu perfil y me gustó tu contenido.", "encontré tu cuenta explorando el nicho.", "excelente trabajo con tus posts.", "veo que estamos en el mismo sector."]
PART_C = ["Te escribo porque tengo una propuesta.", "Me gustaría comentarte algo breve.", "Tengo una idea que podría servirte."]
PART_D = ["Avísame si te interesa.", "Quedo atento.", "Un saludo.", "Espero tu respuesta."]

# PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# RUTAS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')
HISTORY_FILE = os.path.join(SCRIPT_DIR, 'history_dms_sent.txt')

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

def load_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, 'r') as f:
        return set(line.strip() for line in f)

def save_history(username):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{username}\n")

def generate_spintax_message(target_username):
    a = random.choice(PART_A)
    b = random.choice(PART_B)
    c = random.choice(PART_C)
    d = random.choice(PART_D)
    if random.random() > 0.8:
        return f"{a} {target_username}, {b} {c} {d}"
    return f"{a}, {b} {c} {d}"

def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def send_dm_task(account, targets):
    if not account.get('sessionid'): return False

    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- Iniciando Sender: {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument('--lang=es-AR')
    options.add_argument('--no-sandbox')
    
    driver = None
    dms_sent_total = 0
    dms_in_current_batch = 0
    current_batch_limit = random.randint(BATCH_SIZE[0], BATCH_SIZE[1])
    
    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        driver.set_window_size(1280, 900)

        # Login
        driver.get("https://www.instagram.com/404")
        time.sleep(2)
        driver.add_cookie({'name': 'sessionid', 'value': account['sessionid'], 'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True})

        for target in targets:
            if dms_sent_total >= MAX_DMS_PER_ACCOUNT_DAILY:
                print("   [LIMITE] Meta diaria alcanzada.")
                break

            # --- CHEQUEO DE RÁFAGA ---
            if dms_in_current_batch >= current_batch_limit:
                pause_time = random.randint(LONG_PAUSE_TIME[0], LONG_PAUSE_TIME[1])
                print(f"\n   [PAUSA LARGA] Descansando {int(pause_time/60)} minutos para simular comportamiento humano...")
                
                # Opcional: Navegar al Home para parecer activo pero "leyendo"
                driver.get("https://www.instagram.com/")
                time.sleep(pause_time)
                
                # Resetear contadores de lote
                dms_in_current_batch = 0
                current_batch_limit = random.randint(BATCH_SIZE[0], BATCH_SIZE[1])
                print("   [REANUDANDO] Iniciando nueva ráfaga.\n")

            print(f"   >>> Procesando a: {target} (Lote: {dms_in_current_batch + 1}/{current_batch_limit})")
            
            driver.get(f"https://www.instagram.com/{target}/")
            time.sleep(random.uniform(5, 8))

            try:
                wait = WebDriverWait(driver, 8)
                msg_btn_xpath = "//div[text()='Enviar mensaje'] | //div[text()='Message'] | //div[@role='button'][contains(., 'Enviar mensaje')]"
                msg_btn = wait.until(EC.element_to_be_clickable((By.XPATH, msg_btn_xpath)))
                msg_btn.click()
                print("   Entrando al chat...")
                
            except:
                print("   [SKIP] Botón mensaje no disponible.")
                continue

            time.sleep(6)

            # Escribir
            try:
                chat_box = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@contenteditable='true'] | //textarea")))
                
                # A veces hay que hacer click para enfocar
                driver.execute_script("arguments[0].click();", chat_box)
                time.sleep(1)
                
                msg_text = generate_spintax_message(target)
                print(f"   Escribiendo: {msg_text[:30]}...")
                human_type(chat_box, msg_text)
                time.sleep(2)
                
                chat_box.send_keys(Keys.ENTER)
                time.sleep(3)
                print("   [EXITO] Mensaje enviado.")
                
                save_history(target)
                dms_sent_total += 1
                dms_in_current_batch += 1
                
                wait_time = random.randint(TIME_BETWEEN_DMS[0], TIME_BETWEEN_DMS[1])
                print(f"   [SLEEP] {wait_time}s...")
                time.sleep(wait_time)

            except Exception as e:
                print(f"   [ERROR CHAT] {e}")

    except Exception as e:
        print(f"   [CRASH] {e}")

    finally:
        if driver: 
            try: driver.quit()
            except: pass
        if os.path.exists(plugin_path): shutil.rmtree(plugin_path)

def load_csv_targets():
    targets = []
    if os.path.exists(INPUT_CSV):
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            try: next(reader, None) 
            except: pass
            for row in reader:
                if row: targets.append(row[0]) 
    return targets

def main():
    print("--- DM SENDER V2 (MODO RÁFAGA HUMANA) ---")
    
    with open(CUENTAS_FILE, 'r') as f: accounts = json.load(f)
    all_targets = load_csv_targets()
    history = load_history()
    
    pending_targets = [t for t in all_targets if t not in history]
    print(f"Leads Totales: {len(all_targets)} | Pendientes: {len(pending_targets)}")
    
    if not pending_targets: return

    # Para un usuario que envía 100 manuales, podemos ser más agresivos con la distribución
    # Asignamos bloques más grandes
    
    chunk_size = MAX_DMS_PER_ACCOUNT_DAILY
    current_target_index = 0
    
    for acc in accounts:
        if current_target_index >= len(pending_targets): break
        
        batch = pending_targets[current_target_index : current_target_index + chunk_size]
        current_target_index += chunk_size
        
        if batch:
            send_dm_task(acc, batch)
            # Como tardará horas en terminar una cuenta, no necesitamos sleep entre cuentas aquí
            # El script correrá una cuenta hasta terminar su cuota diaria y pasará a la siguiente.

if __name__ == "__main__":
    main()