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
TARGET_PROFILES = ["itsmarcofontana","nat_romo","simonbeingsimon","martonymoral_","sasha.joll","marcomaranghello","lifecoachjesse","juliusfewmd", "profmaximiliancatenacci", "drjoeniamtu", "maxilocaracas"]  
MAX_LEADS_PER_TARGET = 300      
MIN_FOLLOWERS = 2000      
MAX_FOLLOWERS_CAP = 250000 
MIN_POSTS = 100           

# Palabras clave para la nueva columna "Nicho"
TARGET_KEYWORDS = [
    # Nichos originales
    "speaker", "medico", "fitness", "coach", "medic", 
    "influencer", "creator content", "creador de contenido", "podcast",

    # Categoría: Visual Quality & Aesthetics
    "model", "modelo", "fashion", "moda", 
    "architect", "arquitecto", "interior design", "diseñador de interiores",
    "real estate", "bienes raices", "inmobiliaria", "realtor",
    "photographer", "fotografo", "videographer", "filmmaker", "editor", "video editor",

    # Categoría: Authority & Leadership
    "consultant", "consultor", "ceo", "founder", "fundador", 
    "business owner", "dueño de negocio", "entrepreneur", "emprendedor",
    "infoproducer", "infoproductor", "course creator", "creador de cursos",
    "mentor", "mentoring", "public speaker", "conferencista",

    # Categoría: Narrative & Strategy
    "agency owner", "dueño de agencia", "marketing", "marketer", 
    "strategist", "estratega", "brand specialist", "branding"
]

# Si tras 15 scrolls no hay nada nuevo -> Fin de la lista del target
MAX_CONSECUTIVE_EMPTY_SCROLLS = 15 

# Límite de seguridad para rotar cuenta de scraping (no el target)
SAFETY_SESSION_LIMIT = 30

# CREDENCIALES PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# --- GESTIÓN DE RUTAS Y CARPETAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')
RESULTS_DIR = os.path.join(SCRIPT_DIR, "RESULTADOS")

def get_target_paths(target_profile):
    target_dir = os.path.join(RESULTS_DIR, target_profile)
    if not os.path.exists(target_dir):
        try: os.makedirs(target_dir)
        except OSError: pass
    
    csv_file = os.path.join(target_dir, f'leads_seguidos_{target_profile}.csv')
    history_file = os.path.join(target_dir, f'history_scraped_{target_profile}.txt')
    return target_dir, csv_file, history_file

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

def load_history(history_file):
    history = set()
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            for line in f: history.add(line.strip())
    return history

def save_to_history(username, history_file):
    with open(history_file, 'a') as f: f.write(f"{username}\n")

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

def get_niche_match(description_text):
    if not description_text: return "-"
    desc_lower = description_text.lower()
    for kw in TARGET_KEYWORDS:
        if kw.lower() in desc_lower: return kw
    return "-"

def analyze_profile_visual(driver, username):
    try:
        wait = WebDriverWait(driver, 10)
        if "accounts/login" in driver.current_url: return False, 0, 0, "-", "-"
        try:
            meta_element = wait.until(EC.presence_of_element_located((By.XPATH, "//meta[@name='description']")))
            meta_content = meta_element.get_attribute("content").lower()
        except: return False, 0, 0, "-", "-"

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
        niche = get_niche_match(meta_content)

        if not (MIN_FOLLOWERS <= followers <= MAX_FOLLOWERS_CAP):
            print(f"   [X] Followers: {followers}")
            return False, followers, posts, category, niche
        
        if posts < MIN_POSTS:
            print(f"   [X] Inactivo ({posts} posts)")
            return False, followers, posts, category, niche

        print(f"   [OK] LEAD: {username} | F:{followers} | Cat:{category} | Nicho:{niche}")
        return True, followers, posts, category, niche

    except: return False, 0, 0, "-", "-"

def run_scraper_session(account, current_leads_count, target_profile):
    """
    Retorna (bool, int):
    - True: El target ya no tiene más datos o se terminó (Lista fin o Max Leads).
    - False: La sesión terminó por seguridad (limite 30), pero el target sigue vivo.
    """
    if not account.get('sessionid'): return False, 0
    _, csv_filename, history_file = get_target_paths(target_profile)

    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- [TARGET: {target_profile}] Iniciando sesión con {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking") 
    options.add_argument('--lang=en-US')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless=new')  
    
    driver = None
    leads_added_this_session = 0

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        driver.set_window_size(412, 915) 

        driver.get("https://www.instagram.com/404") 
        time.sleep(2)
        driver.add_cookie({'name': 'sessionid', 'value': account['sessionid'], 'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True})

        print(f"Yendo a {target_profile}...")
        driver.get(f"https://www.instagram.com/{target_profile}/")
        time.sleep(5)
        
        if "login" in driver.current_url:
            print("[ERROR] SessionID inválida.")
            return False, 0

        dismiss_popups(driver)
        try:
            following_link = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(@href, 'following')]")))
            following_link.click()
            print("Lista abierta.")
        except:
            print("[ERROR] No se pudo abrir la lista.")
            return False, 0

        time.sleep(3)
        analyzed_history = load_history(history_file)
        consecutive_fails = 0
        IGNORE = [target_profile, account['user']]
        
        try: dialog_box = driver.find_element(By.XPATH, "//div[@role='dialog']")
        except: return False, 0

        while (current_leads_count + leads_added_this_session) < MAX_LEADS_PER_TARGET:
            dismiss_popups(driver)
            
            try: elements = dialog_box.find_elements(By.TAG_NAME, "a")
            except: break
            
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
                    if user.isdigit() or user in IGNORE or len(user) < 3: continue
                    if not elem.text.strip(): continue

                    if user not in analyzed_history:
                        new_candidates.append(user)
                        analyzed_history.add(user) 
                except: pass
            
            # --- DETECCION DE FIN DE LISTA / BLOQUEO ---
            if not new_candidates:
                consecutive_fails += 1
                print(f"   [!] Scroll sin nuevos leads ({consecutive_fails}/{MAX_CONSECUTIVE_EMPTY_SCROLLS})...")
                
                if consecutive_fails >= MAX_CONSECUTIVE_EMPTY_SCROLLS:
                    print(f"   [STOP] No se encuentran nuevos usuarios tras {MAX_CONSECUTIVE_EMPTY_SCROLLS} intentos.")
                    print("   >>> Fin de lista o Bloqueo. Pasando al siguiente Target.")
                    return True, leads_added_this_session
                
                if last_element_found:
                    try: driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
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
                save_to_history(user, history_file)

                try:
                    driver.execute_script("window.open('about:blank', '_blank');")
                    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(f"https://www.instagram.com/{user}/")
                    
                    is_valid, num_f, num_p, cat, niche = analyze_profile_visual(driver, user)
                    
                    driver.close()
                    driver.switch_to.window(main_window)
                    
                    if is_valid:
                        leads_added_this_session += 1
                        total_now = current_leads_count + leads_added_this_session
                        
                        print(f"   >>> [PROGRESO] {total_now}/{MAX_LEADS_PER_TARGET} Leads para {target_profile}")
                        
                        with open(csv_filename, 'a', newline='', encoding='utf-8-sig') as f:
                            writer = csv.writer(f, delimiter=';')
                            writer.writerow([user, f"https://instagram.com/{user}", num_f, num_p, cat, niche, "FOLLOWING"])
                        
                        if total_now >= MAX_LEADS_PER_TARGET:
                            return True, leads_added_this_session

                    time.sleep(random.uniform(2, 4)) 
                except Exception as e:
                    print(f" [SKIP] Err: {e}")
                    try:
                        while len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.close()
                        driver.switch_to.window(main_window)
                    except: return False, leads_added_this_session

            if last_element_found:
                try: driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                except: pass
            
            time.sleep(random.uniform(1.5, 3))
            
            # --- SEGURIDAD DE SESIÓN (RESTABLECIDA) ---
            if leads_added_this_session >= SAFETY_SESSION_LIMIT:
                print(f"   [SEGURIDAD] Límite de {SAFETY_SESSION_LIMIT} leads por sesión alcanzado. Rotando cuenta...")
                return False, leads_added_this_session

        return True, leads_added_this_session

    except Exception as e:
        print(f"[ERROR CRITICO] {e}")
        return False, leads_added_this_session

    finally:
        if driver: 
            try: driver.quit()
            except: pass
        if os.path.exists(plugin_path): shutil.rmtree(plugin_path)

def main():
    print(f"--- SCRAPER MULTI-TARGET ---")
    accounts = load_accounts()
    if not accounts: return

    scraper_acc_index = 0

    for target in TARGET_PROFILES:
        _, csv_filename, _ = get_target_paths(target)
        if not os.path.exists(csv_filename):
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(["Usuario", "URL", "Seguidores", "Publicaciones", "Categoria", "Nicho", "Origen"])

        current_leads = 0
        if os.path.exists(csv_filename):
            with open(csv_filename, 'r', encoding='utf-8-sig') as f:
                rows = list(csv.reader(f, delimiter=';'))
                current_leads = max(0, len(rows) - 1)
        
        print(f"\n>>> PROCESANDO TARGET: {target} | Leads actuales: {current_leads}/{MAX_LEADS_PER_TARGET}")

        if current_leads >= MAX_LEADS_PER_TARGET: continue

        while current_leads < MAX_LEADS_PER_TARGET:
            if scraper_acc_index >= len(accounts):
                print("Ciclo de cuentas terminado. Esperando 5 min...")
                time.sleep(300)
                scraper_acc_index = 0
            
            current_acc = accounts[scraper_acc_index]
            success, leads_found_session = run_scraper_session(current_acc, current_leads, target)
            current_leads += leads_found_session
            
            if current_leads >= MAX_LEADS_PER_TARGET: break
            
            # Si success es True, significa que se agotó la lista o hubo bloqueo de carga
            # por lo tanto debemos romper el bucle y pasar al SIGUIENTE TARGET.
            if success:
                print(f"   Target {target} finalizado (objetivo alcanzado o lista agotada).")
                break 
            
            # Si success es False, significa rotación por seguridad (30 leads) o error puntual,
            # seguimos en el bucle 'while' con el MISMO TARGET pero cambiamos de cuenta.
            scraper_acc_index += 1
            print(f"   Cambiando cuenta de scraping (mismo Target)...")
            time.sleep(5)

if __name__ == "__main__":
    main()