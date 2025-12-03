import time
import csv
import os
import random
import shutil
import re
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- CONFIGURACIÓN ---
TARGET_PROFILE = "mickunplugged"  
MAX_LEADS = 200          
MIN_FOLLOWERS = 2000      
MAX_FOLLOWERS_CAP = 250000 
MIN_POSTS = 100           

# CREDENCIALES PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# --- GESTIÓN DE RUTAS Y CARPETAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

RESULTS_DIR = os.path.join(SCRIPT_DIR, "RESULTADOS")
TARGET_DIR = os.path.join(RESULTS_DIR, TARGET_PROFILE)

if not os.path.exists(TARGET_DIR):
    try:
        os.makedirs(TARGET_DIR)
        print(f"--- [SISTEMA] Carpeta creada: {TARGET_DIR} ---")
    except OSError as e:
        print(f"[ERROR] No se pudo crear la carpeta: {e}")

CSV_FILENAME = os.path.join(TARGET_DIR, f'leads_seguidos_{TARGET_PROFILE}.csv')
HISTORY_FILE = os.path.join(TARGET_DIR, f'history_scraped_{TARGET_PROFILE}.txt')

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
    if not os.path.exists(CUENTAS_FILE):
        print(f"[ERROR] No se encontró: {CUENTAS_FILE}")
        return []
    try:
        with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                print(f"[OK] JSON cargado correctamente ({len(data)} cuentas).")
                return data
            return []
    except Exception as e:
        print(f"[ERROR] {e}")
        return []

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

def dismiss_popups(driver):
    buttons_text = ["Not Now", "Ahora no", "Cancel", "Cancelar", "Not now", "ahora no"]
    for _ in range(2):
        found = False
        for txt in buttons_text:
            try:
                xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                for btn in elements:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
                        found = True
            except: pass
        if not found: break

def extract_category(driver):
    category = "-"
    try:
        elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'x7a106z')] | //div[contains(@class, 'x1re03b8')]")
        for el in elements:
            text = el.text.strip()
            if text and len(text) < 40 and not any(char.isdigit() for char in text):
                if "seguido" in text.lower() or "followed" in text.lower(): continue
                category = text
                break
        
        if category == "-":
            links = driver.find_elements(By.XPATH, "//a[contains(@href, '/explore/locations/') or contains(@href, '/explore/tags/')]")
            for link in links:
                if link.text.strip() and len(link.text) > 3:
                    category = link.text.strip()
                    break
    except: pass
    return category

def analyze_profile_visual(driver, username):
    try:
        # Aumentamos timeout a 10s para perfiles lentos
        wait = WebDriverWait(driver, 10)
        
        # Check rápido de login fallido
        if "accounts/login" in driver.current_url: return False, 0, 0, "-"
            
        try:
            meta_element = wait.until(EC.presence_of_element_located((By.XPATH, "//meta[@name='description']")))
            meta_content = meta_element.get_attribute("content").lower()
        except: return False, 0, 0, "-"

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

        category = extract_category(driver)

        if not (MIN_FOLLOWERS <= followers <= MAX_FOLLOWERS_CAP):
            print(f"   [X] Followers: {followers}")
            return False, followers, posts, category
        
        if posts < MIN_POSTS:
            print(f"   [X] Inactivo ({posts} posts)")
            return False, followers, posts, category

        print(f"   [OK] LEAD: {username} | F:{followers} | Cat:{category}")
        return True, followers, posts, category

    except:
        return False, 0, 0, "-"

def run_scraper_session(account, total_leads_found):
    if not account.get('sessionid'): return False

    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- Iniciando sesión con {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking") # Fuerza bruta anti-popups
    options.add_argument('--lang=en-US')
    options.add_argument('--no-sandbox')
    
    driver = None
    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        driver.set_window_size(412, 915)

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

        print(f"Yendo a {TARGET_PROFILE}...")
        driver.get(f"https://www.instagram.com/{TARGET_PROFILE}/")
        time.sleep(5)
        
        if "login" in driver.current_url:
            print("[ERROR] SessionID inválida.")
            return False

        dismiss_popups(driver)

        try:
            print("Abriendo lista...")
            following_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//a[contains(@href, 'following')]"))
            )
            following_link.click()
            print("Lista abierta.")
        except:
            print("[ERROR] No se pudo abrir la lista.")
            return False 

        time.sleep(3)

        analyzed_history = load_history()
        consecutive_fails = 0
        leads_in_session = 0
        
        print(f"--- ANALIZANDO... ---")
        
        IGNORE = [TARGET_PROFILE, account['user']]

        try:
            dialog_box = driver.find_element(By.XPATH, "//div[@role='dialog']")
        except:
            print("No se detectó el cuadro de diálogo.")
            return False

        while total_leads_found < MAX_LEADS:
            dismiss_popups(driver)
            
            try:
                elements = dialog_box.find_elements(By.TAG_NAME, "a")
            except:
                print("El diálogo se cerró o cambió.")
                break
            
            new_candidates = []
            last_element_found = None

            for elem in elements:
                try:
                    last_element_found = elem
                    
                    href = elem.get_attribute('href')
                    if not href or 'instagram.com/' not in href: continue
                    
                    clean_href = href.split('?')[0].rstrip('/')
                    user = clean_href.split('/')[-1]
                    
                    if any(x in clean_href for x in ['/p/', '/reels/', '/stories/', '/explore/', '/direct/']): continue
                    if user.isdigit(): continue 
                    if user in IGNORE or len(user) < 3: continue
                    
                    if not elem.text.strip(): continue

                    if user not in analyzed_history:
                        new_candidates.append(user)
                        analyzed_history.add(user) 
                except: pass
            
            if not new_candidates:
                consecutive_fails += 1
                if consecutive_fails > 10:
                    print("Fin de lista o bloqueo.")
                    return True 
                
                # Scroll
                if last_element_found:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                    except: pass
                else:
                    try: dialog_box.send_keys(Keys.END)
                    except: pass
                
                time.sleep(2)
                continue
            
            consecutive_fails = 0
            main_window = driver.current_window_handle
            
            for user in new_candidates:
                print(f"Analizando: {user}...", end="")
                save_to_history(user)

                try:
                    # ESTRATEGIA STABLE: Abrir en blanco -> Navegar
                    driver.execute_script("window.open('about:blank', '_blank');")
                    
                    # Esperar pestaña (10s)
                    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])
                    
                    # Cargar Perfil
                    driver.get(f"https://www.instagram.com/{user}/")
                    
                    is_valid, num_f, num_p, cat = analyze_profile_visual(driver, user)
                    
                    # Cerrar y volver
                    driver.close()
                    driver.switch_to.window(main_window)
                    
                    if is_valid:
                        total_leads_found += 1
                        leads_in_session += 1
                        with open(CSV_FILENAME, 'a', newline='', encoding='utf-8-sig') as f:
                            writer = csv.writer(f, delimiter=';')
                            writer.writerow([user, f"https://instagram.com/{user}", num_f, num_p, cat, "FOLLOWING"])
                        
                        if total_leads_found >= MAX_LEADS: return True

                    time.sleep(random.uniform(2, 4)) 

                except Exception as e:
                    print(f" [SKIP] Error: {e}")
                    # Recuperación de emergencia
                    try:
                        while len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.close()
                        driver.switch_to.window(main_window)
                    except: 
                        return False 

            if last_element_found:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                except: pass
            
            time.sleep(random.uniform(1.5, 3))
            
            if leads_in_session > 30: 
                print("Rotando cuenta por seguridad...")
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
    print(f"--- SCRAPER SEGUIDOS (DIR: {RESULTS_DIR}) ---")
    
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Usuario", "URL", "Seguidores", "Publicaciones", "Categoria", "Origen"])
    
    current_leads = 0
    if os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
            rows = list(csv.reader(f, delimiter=';'))
            current_leads = max(0, len(rows) - 1)
    
    accounts = load_accounts()
    
    if not accounts:
        print("ERROR: No hay cuentas válidas en cuentas.json")
        return

    print(f"Cargadas {len(accounts)} cuentas con SessionID.")

    acc_index = 0
    while current_leads < MAX_LEADS:
        if acc_index >= len(accounts):
            print("Ciclo de cuentas terminado. Esperando 5 min...")
            time.sleep(300)
            acc_index = 0
        
        current_acc = accounts[acc_index]
        success = run_scraper_session(current_acc, current_leads)
        
        if success and current_leads >= MAX_LEADS:
            break
        
        acc_index += 1
        with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
            rows = list(csv.reader(f, delimiter=';'))
            current_leads = max(0, len(rows) - 1)
        
        print(f"Total Leads: {current_leads}/{MAX_LEADS}. Cambiando cuenta...")
        time.sleep(5)

if __name__ == "__main__":
    main()