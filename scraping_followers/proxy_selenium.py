import time
import csv
import os
import random
import shutil
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- CONFIGURACIÓN ---
TARGET_PROFILE = "mickunplugged"
MAX_LEADS = 200          # Meta de leads a guardar
MIN_FOLLOWERS = 2000      # Mínimo seguidores del lead
MAX_FOLLOWERS_CAP = 250000 
MIN_POSTS = 100           

# CREDENCIALES PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# RUTAS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.txt')
CSV_FILENAME = os.path.join(SCRIPT_DIR, f'leads_seguidos_{TARGET_PROFILE}.csv')
HISTORY_FILE = os.path.join(SCRIPT_DIR, f'history_scraped_{TARGET_PROFILE}.txt')

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
    accs = []
    if os.path.exists(CUENTAS_FILE):
        with open(CUENTAS_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 2:
                    accs.append({'user': parts[0], 'pass': parts[1]})
    return accs

def load_history():
    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            for line in f:
                history.add(line.strip())
    return history

def save_to_history(username):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{username}\n")

def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

# --- NUEVA FUNCIÓN PARA CERRAR POPUPS ---
def dismiss_popups(driver):
    """Cierra cualquier ventana emergente de IG (Notificaciones, Guardar Login, etc)."""
    # Textos comunes de botones para cerrar
    buttons_text = [
        "Not Now", "Ahora no", "Cancel", "Cancelar", 
        "Not now", "ahora no", "Allow", "Permitir",
        "Add to Home Screen", "Añadir a pantalla de inicio"
    ]
    
    # Intentamos 3 veces por si hay varios popups apilados
    for _ in range(3):
        found = False
        for txt in buttons_text:
            try:
                # Busca botones o divs clickeables con el texto
                xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                for btn in elements:
                    if btn.is_displayed():
                        print(f"   [POPUP] Cerrando: {txt}")
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                        found = True
            except: pass
        if not found: break
        time.sleep(0.5)

def analyze_profile_visual(driver, username):
    try:
        wait = WebDriverWait(driver, 8)
        if "accounts/login" in driver.current_url: return False, 0, 0
            
        try:
            meta_element = wait.until(EC.presence_of_element_located((By.XPATH, "//meta[@name='description']")))
            meta_content = meta_element.get_attribute("content").lower()
        except: return False, 0, 0

        followers = 0
        posts = 0

        f_match = re.search(r'([0-9\.,km]+)\s*(followers|seguidores)', meta_content)
        p_match = re.search(r'([0-9\.,km]+)\s*(posts|publicaciones)', meta_content)

        if f_match:
            raw = f_match.group(1).replace(',', '')
            if 'k' in raw: followers = int(float(raw.replace('k', '')) * 1000)
            elif 'm' in raw: followers = int(float(raw.replace('m', '')) * 1000000)
            else: followers = int(raw.replace('.', ''))
        
        if p_match:
            raw = p_match.group(1).replace(',', '')
            if 'k' in raw: posts = int(float(raw.replace('k', '')) * 1000)
            else: posts = int(raw.replace('.', ''))

        if followers < MIN_FOLLOWERS:
            print(f"   [X] Muy chico ({followers}): {username}")
            return False, followers, posts
        
        if followers > MAX_FOLLOWERS_CAP:
            print(f"   [X] Muy grande ({followers}): {username}")
            return False, followers, posts
        
        if posts < MIN_POSTS:
            print(f"   [X] Inactivo ({posts}): {username}")
            return False, followers, posts

        print(f"   [OK] LEAD CALIFICADO: {username} ({followers} segs)")
        return True, followers, posts

    except Exception:
        return False, 0, 0

def run_scraper_session(account, total_leads_found):
    session_id = str(random.randint(100000, 999999))
    print(f"\n--- Iniciando sesión con {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument('--lang=en-US')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage') 
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-popup-blocking') 
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-quic')
    options.add_argument('--user-agent=Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36')

    driver = None
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.set_window_size(412, 915)

        # LOGIN
        print("Login...")
        driver.get("https://www.instagram.com/accounts/login/")
        wait = WebDriverWait(driver, 25)
        time.sleep(3)
        try: driver.find_element(By.XPATH, "//button[contains(text(), 'Allow')]").click()
        except: pass

        user_input = wait.until(EC.visibility_of_element_located((By.NAME, "username")))
        human_type(user_input, account['user'])
        human_type(driver.find_element(By.NAME, "password"), account['pass'])
        driver.find_element(By.NAME, "password").send_keys(Keys.ENTER)
        
        time.sleep(10)
        
        # --- LIMPIEZA DE POPUPS DESPUES DEL LOGIN ---
        dismiss_popups(driver)
        # --------------------------------------------

        # TARGET
        print(f"Yendo a {TARGET_PROFILE}...")
        driver.get(f"https://www.instagram.com/{TARGET_PROFILE}/")
        time.sleep(5)
        
        # Limpieza por si salen popups al cargar perfil
        dismiss_popups(driver)

        # --- ABRIR LISTA DE SEGUIDOS (FOLLOWING) ---
        try:
            print("Abriendo lista de SEGUIDOS...")
            following_link = driver.find_element(By.XPATH, f"//a[contains(@href, 'following')]")
            following_link.click()
            print("Lista abierta.")
        except:
            print("[ERROR] No se pudo abrir la lista de seguidos (Verifica si es publica).")
            return False 

        time.sleep(4)

        analyzed_history = load_history()
        consecutive_fails = 0
        leads_in_session = 0
        
        print(f"--- ANALIZANDO SEGUIDOS (Total: {total_leads_found}) ---")
        
        IGNORE = [TARGET_PROFILE, account['user'], 'home', 'reels', 'create', 'search', 'explore', 'direct', 'inbox']

        while total_leads_found < MAX_LEADS:
            # Limpieza periódica de popups
            dismiss_popups(driver)
            
            elements = driver.find_elements(By.XPATH, "//a[not(contains(@href, 'explore')) and not(contains(@href, 'following'))]")
            
            new_candidates = []
            for elem in elements:
                try:
                    href = elem.get_attribute('href')
                    if href and 'instagram.com/' in href:
                        user = href.strip('/').split('/')[-1]
                        
                        if user in IGNORE: continue
                        if len(user) > 30 or '?' in user: continue

                        if user not in analyzed_history:
                            new_candidates.append(user)
                            analyzed_history.add(user) 
                except: pass
            
            if not new_candidates:
                consecutive_fails += 1
                if consecutive_fails > 10:
                    print("Fin de scroll o bloqueo.")
                    return True 
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                continue
            
            consecutive_fails = 0
            main_window = driver.current_window_handle
            
            for user in new_candidates:
                print(f"Analizando: {user}...", end="")
                save_to_history(user)

                try:
                    driver.execute_script(f"window.open('https://www.instagram.com/{user}/', '_blank');")
                    WebDriverWait(driver, 5).until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])
                    
                    is_valid, num_f, num_p = analyze_profile_visual(driver, user)
                    
                    driver.close()
                    driver.switch_to.window(main_window)
                    
                    if is_valid:
                        total_leads_found += 1
                        leads_in_session += 1
                        with open(CSV_FILENAME, 'a', newline='', encoding='utf-8-sig') as f:
                            writer = csv.writer(f, delimiter=';')
                            writer.writerow([user, f"https://instagram.com/{user}", num_f, num_p, "FOLLOWING"])
                        
                        if total_leads_found >= MAX_LEADS: return True

                    time.sleep(random.uniform(1.5, 3))

                except Exception as e:
                    print(f" [SKIP] Error Pestaña")
                    try:
                        if len(driver.window_handles) > 1:
                            for h in driver.window_handles[1:]:
                                driver.switch_to.window(h)
                                driver.close()
                        driver.switch_to.window(main_window)
                    except: return False 

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            
            if leads_in_session > 40:
                print("Límite por cuenta alcanzado. Rotando...")
                return False 

        return True 

    except Exception as e:
        print(f"[ERROR CRITICO] {e}")
        return False 

    finally:
        if driver: 
            try: driver.quit()
            except: pass
        if os.path.exists(plugin_path): shutil.rmtree(plugin_path)

def main():
    print("--- SCRAPER SEGUIDOS (CON AUTO-CIERRE POPUPS) ---")
    
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Usuario", "URL", "Seguidores", "Publicaciones", "Origen"])
    
    current_leads = 0
    with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
        current_leads = sum(1 for row in csv.reader(f, delimiter=';')) - 1
        if current_leads < 0: current_leads = 0
    
    accounts = load_accounts()
    if not accounts:
        print("Sin cuentas.")
        return

    acc_index = 0
    while current_leads < MAX_LEADS:
        if acc_index >= len(accounts):
            print("Ciclo terminado. Esperando 5 min...")
            time.sleep(300)
            acc_index = 0
        
        current_acc = accounts[acc_index]
        success = run_scraper_session(current_acc, current_leads)
        
        if success and current_leads >= MAX_LEADS:
            break
        
        acc_index += 1
        with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
            current_leads = sum(1 for row in csv.reader(f, delimiter=';')) - 1
        
        print(f"Total Leads: {current_leads}/{MAX_LEADS}. Cambiando cuenta...")
        time.sleep(5)

if __name__ == "__main__":
    main()