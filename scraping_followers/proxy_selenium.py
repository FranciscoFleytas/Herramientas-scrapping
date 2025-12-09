import time
import csv
import os
import random
import shutil
import re
import json
import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# --- CONFIGURACIÓN ---
TARGET_PROFILES = ["shivanisikri","ergogenic_health","jacoblovesbeingalive","miss.kiaraphillips","christinecampbellpate","carolinemiddelsdorf","vaginacoach","the.biohackingconference", "coach_jerrykuykendall","drhalland","lizbagwell7","shaeleonard","jennamcinnes","ththetrailtohealthesoulhakker"]  
MAX_LEADS_PER_TARGET = 300      
MIN_FOLLOWERS = 2000      
MAX_FOLLOWERS_CAP = 150000 
MIN_POSTS = 100           
MAX_ENGAGEMENT_THRESHOLD = 3.0 
MAX_CONSECUTIVE_EMPTY_SCROLLS = 15 
SAFETY_SESSION_LIMIT = 30

# PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# --- MAPEO DE NICHOS ---
NICHE_MAPPING = {
    "Salud & Medicina": ["medico", "doctor", "medic", "surgeon", "cirujano", "dermatologist", "dentist", "dentista", "nutritionist", "nutricionista", "wellness", "bienestar", "mental health", "pediatrician"],
    "Real Estate & Arquitectura": ["real estate", "bienes raices", "realtor", "architect", "arquitecto", "interior design", "property", "broker", "construction"],
    "Negocios & Emprendimiento": ["ceo", "founder", "fundador", "business owner", "entrepreneur", "emprendedor", "consultant", "startup", "director", "manager", "leader"],
    "Marketing & Ventas": ["marketing", "marketer", "sales", "ventas", "closer", "copywriter", "seo", "media buyer", "social media manager", "digital marketing", "ads"],
    "Finanzas & Inversiones": ["investor", "inversor", "trader", "crypto", "financial advisor", "finance", "finanzas", "accountant", "wealth", "bitcoin", "economist"],
    "Educación & Coaching": ["coach", "mentor", "teacher", "profesor", "educator", "trainer", "academy", "speaker", "author"],
    "Creadores & Influencers": ["influencer", "creator", "creador", "podcast", "ugc", "blogger", "youtuber", "content"],
    "Moda & Belleza": ["model", "modelo", "fashion", "moda", "stylist", "makeup", "beauty", "skincare", "salon", "clothing"],
    "Arte & Creatividad": ["photographer", "fotografo", "videographer", "filmmaker", "designer", "artist", "writer", "producer", "music"],
    "Tecnología & Software": ["tech", "saas", "software", "developer", "cto", "engineer", "ingeniero", "ai", "programmer"],
    "Lifestyle, Fitness & Food": ["fitness", "gym", "trainer", "yoga", "chef", "foodie", "travel", "luxury", "lifestyle"]
}

# --- GESTIÓN DE RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')
RESULTS_DIR = os.path.join(SCRIPT_DIR, "RESULTADOS")

if not os.path.exists(RESULTS_DIR):
    try: os.makedirs(RESULTS_DIR)
    except OSError: pass

GLOBAL_HISTORY_FILE = os.path.join(RESULTS_DIR, "history_global.txt")
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
SESSION_CSV_FILE = os.path.join(RESULTS_DIR, f"leads_export_{timestamp}.csv")

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

def load_global_history():
    history = set()
    if os.path.exists(GLOBAL_HISTORY_FILE):
        with open(GLOBAL_HISTORY_FILE, 'r') as f:
            for line in f: history.add(line.strip())
    return history

def save_to_global_history(username):
    with open(GLOBAL_HISTORY_FILE, 'a') as f: f.write(f"{username}\n")

def dismiss_popups(driver):
    try:
        WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.XPATH, "//button[text()='Not Now' or text()='Ahora no']"))
        )
        buttons_text = ["Not Now", "Ahora no", "Cancel", "Cancelar"]
        for txt in buttons_text:
            xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"
            elements = driver.find_elements(By.XPATH, xpath)
            for btn in elements:
                driver.execute_script("arguments[0].click();", btn)
    except: 
        pass

def extract_category(driver):
    category = "-"
    try:
        elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'x7a106z')]")
        for el in elements:
            text = el.text.strip()
            if text and len(text) < 40 and not any(char.isdigit() for char in text):
                if "seguido" not in text.lower():
                    category = text
                    break
    except: pass
    return category

def get_niche_match(description_text):
    if not description_text: return "-"
    desc_lower = description_text.lower()
    for niche_name, keywords in NICHE_MAPPING.items():
        for kw in keywords:
            if kw.lower() in desc_lower:
                return niche_name 
    return "-"

def parse_social_number(text):
    if not text: return 0
    text = str(text).lower().replace(',', '')
    try:
        if 'k' in text:
            return int(float(text.replace('k', '')) * 1000)
        elif 'm' in text:
            return int(float(text.replace('m', '')) * 1000000)
        else:
            clean_num = re.sub(r'[^\d.]', '', text)
            return int(float(clean_num))
    except:
        return 0

def calculate_real_engagement(driver, followers):
    """
    Retorna float con el % de engagement O retorna el string "Comentarios Ocultos"
    si se detecta privacidad activada.
    """
    try:
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/p/')]")))
        except: return 0.0

        posts_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
        if len(posts_links) < 4: return 0.0 

        # 4to Post
        target_link = posts_links[3]
        driver.execute_script("arguments[0].click();", target_link)
        
        content_text = ""
        try:
            wait = WebDriverWait(driver, 5)
            modal_element = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, '_ae2s')] | //ul[contains(@class, '_a9ym')] | //div[@role='dialog']")
            ))
            content_text = modal_element.get_attribute("innerText").lower()
        except:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            return 0.0

        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        
        likes = 0
        comments = 0
        
        match_std = re.search(r'([\d.,kkm]+)\s*(?:likes|me gusta|j’aime)', content_text)
        match_hidden_partial = re.search(r'(?:y|and)\s+([\d.,kkm]+)\s+(?:personas|others)', content_text)

        if match_std:
            likes = parse_social_number(match_std.group(1))
        elif match_hidden_partial:
            likes = parse_social_number(match_hidden_partial.group(1))

        c_match = re.search(r'([\d.,kkm]+)\s*(?:comments|comentarios)', content_text)
        if c_match: 
            comments = parse_social_number(c_match.group(1))

        # --- LÓGICA COMENTARIOS OCULTOS ---
        # Si no hay likes numéricos Y dice "otras personas" -> Retornar texto especial
        if likes == 0 and ("otras personas" in content_text or "others" in content_text):
            return "Comentarios Ocultos"
        
        total = likes + comments
        if followers == 0: return 0.0
        
        engagement_rate = (total / followers) * 100
        return round(engagement_rate, 2)

    except:
        try: ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except: pass
        return 0.0

def analyze_profile_visual(driver, username):
    try:
        wait = WebDriverWait(driver, 4) 
        if "accounts/login" in driver.current_url: return False, 0, 0, "-", "-", 0
        
        try:
            meta_element = wait.until(EC.presence_of_element_located((By.XPATH, "//meta[@name='description']")))
            meta_content = meta_element.get_attribute("content").lower()
        except: return False, 0, 0, "-", "-", 0

        followers = 0
        posts = 0
        f_match = re.search(r'([0-9\.,km]+)\s*(followers|seguidores)', meta_content)
        p_match = re.search(r'([0-9\.,km]+)\s*(posts|publicaciones)', meta_content)

        if f_match: followers = parse_social_number(f_match.group(1))
        if p_match: posts = parse_social_number(p_match.group(1))

        if not (MIN_FOLLOWERS <= followers <= MAX_FOLLOWERS_CAP):
            return False, followers, posts, "-", "-", 0
        
        if posts < MIN_POSTS:
            return False, followers, posts, "-", "-", 0
            
        engagement = calculate_real_engagement(driver, followers)
        category = extract_category(driver)
        niche = get_niche_match(meta_content)
        
        # --- MANEJO DE RESULTADO DE ENGAGEMENT ---
        
        # Caso 1: String "Comentarios Ocultos"
        if isinstance(engagement, str):
            print(f"   [OK] LEAD: {username} | F:{followers} | Eng:{engagement} | Nicho:{niche}")
            # Lo consideramos VÁLIDO porque no podemos probar que sea malo
            return True, followers, posts, category, niche, engagement

        # Caso 2: Flotante normal (verificación de threshold)
        if isinstance(engagement, (int, float)):
            if engagement >= MAX_ENGAGEMENT_THRESHOLD:
                print(f"   [X] High Eng: {engagement}%")
                return False, followers, posts, category, niche, engagement

            print(f"   [OK] LEAD: {username} | F:{followers} | Eng:{engagement}% | Nicho:{niche}")
            return True, followers, posts, category, niche, engagement

        return False, 0, 0, "-", "-", 0

    except: return False, 0, 0, "-", "-", 0

def run_scraper_session(account, current_leads_count, target_profile):
    if not account.get('sessionid'): return False, 0
    
    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- [TARGET: {target_profile}] Login: {account['user']} ---")
    
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument('--lang=en-US')
    options.add_argument('--no-sandbox')
    
    # --- MODO INVISIBLE (SECUNDARIO) ---
    options.add_argument('--headless=new')
    
    options.page_load_strategy = 'eager'
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)  
    
    driver = None
    leads_added_this_session = 0

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        # Tamaño escritorio necesario para que el modal funcione aunque esté headless
        driver.set_window_size(1280, 800) 

        driver.get("https://www.instagram.com/404") 
        time.sleep(1)
        driver.add_cookie({'name': 'sessionid', 'value': account['sessionid'], 'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True})

        print(f"Yendo a {target_profile}...")
        driver.get(f"https://www.instagram.com/{target_profile}/")
        
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//header")))
        except:
            time.sleep(2) 

        if "login" in driver.current_url:
            print("[ERROR] SessionID inválida.")
            return False, 0

        dismiss_popups(driver)
        try:
            following_link = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(@href, 'following')]")))
            following_link.click()
            print("Lista abierta.")
        except:
            print("[ERROR] Lista oculta/privada.")
            return False, 0

        time.sleep(2)
        
        analyzed_history = load_global_history()
        consecutive_fails = 0
        IGNORE = [target_profile, account['user']]
        
        try: 
            dialog_box = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
        except: return False, 0

        while (current_leads_count + leads_added_this_session) < MAX_LEADS_PER_TARGET:
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
                    if len(user) < 3 or user in IGNORE: continue
                    if any(x in clean_href for x in ['/p/', '/explore/', '/direct/']): continue
                    
                    if user not in analyzed_history:
                        new_candidates.append(user)
                        analyzed_history.add(user) 
                except: pass
            
            if not new_candidates:
                consecutive_fails += 1
                if consecutive_fails >= MAX_CONSECUTIVE_EMPTY_SCROLLS:
                    print(f"   [STOP] Fin de lista o límite de scrolls.")
                    return True, leads_added_this_session
                
                if last_element_found:
                    driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                time.sleep(1.5)
                continue
            
            consecutive_fails = 0
            main_window = driver.current_window_handle
            
            for user in new_candidates:
                save_to_global_history(user)

                try:
                    driver.execute_script("window.open('about:blank', '_blank');")
                    WebDriverWait(driver, 3).until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])
                    
                    driver.get(f"https://www.instagram.com/{user}/")
                    
                    is_valid, num_f, num_p, cat, niche, eng_rate = analyze_profile_visual(driver, user)
                    
                    try: driver.close()
                    except: pass
                    
                    driver.switch_to.window(main_window)
                    
                    if is_valid:
                        leads_added_this_session += 1
                        total_now = current_leads_count + leads_added_this_session
                        
                        # Formato de engagement en CSV: String directo o porcentaje
                        eng_str = eng_rate if isinstance(eng_rate, str) else f"{eng_rate}%"

                        with open(SESSION_CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f:
                            writer = csv.writer(f, delimiter=';')
                            writer.writerow([user, f"https://instagram.com/{user}", num_f, num_p, cat, niche, eng_str, target_profile])
                        
                        if total_now >= MAX_LEADS_PER_TARGET:
                            return True, leads_added_this_session

                    time.sleep(random.uniform(0.5, 1.2)) 
                    
                except Exception as e:
                    print(f"   [SKIP] Error: {e}")
                    try:
                        while len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.close()
                        driver.switch_to.window(main_window)
                    except: pass

            if last_element_found:
                driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
            
            time.sleep(1)
            
            if leads_added_this_session >= SAFETY_SESSION_LIMIT:
                print(f"   [SEGURIDAD] Rotando cuenta tras {SAFETY_SESSION_LIMIT} leads.")
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

def get_current_leads_count_global(target_name):
    count = 0
    if not os.path.exists(RESULTS_DIR): return 0
    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".csv")]
    for filename in files:
        filepath = os.path.join(RESULTS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=';')
                try: next(reader) 
                except: continue
                for row in reader:
                    if row and len(row) > 0:
                        if row[-1] == target_name: count += 1
        except: continue
    return count

def main():
    print(f"--- SCRAPER OPTIMIZADO V5 (HEADLESS + COMENTARIOS OCULTOS) ---")
    
    accounts = load_accounts()
    if not accounts: 
        print("Error: No hay cuentas en cuentas.json")
        return

    if not os.path.exists(SESSION_CSV_FILE):
        with open(SESSION_CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Usuario", "URL", "Seguidores", "Publicaciones", "Categoria", "Nicho", "Engagement", "Origen"])

    scraper_acc_index = 0

    for target in TARGET_PROFILES:
        current_leads = get_current_leads_count_global(target)
        print(f"\n>>> TARGET: {target} | Actuales: {current_leads}/{MAX_LEADS_PER_TARGET}")

        if current_leads >= MAX_LEADS_PER_TARGET: continue
        
        target_fail_count = 0

        while current_leads < MAX_LEADS_PER_TARGET:
            if scraper_acc_index >= len(accounts):
                print("Esperando 5 min por rotación completa...")
                time.sleep(300)
                scraper_acc_index = 0
            
            current_acc = accounts[scraper_acc_index]
            success, leads_found_session = run_scraper_session(current_acc, current_leads, target)
            current_leads += leads_found_session
            
            if not success and leads_found_session == 0:
                target_fail_count += 1
                if target_fail_count >= len(accounts):
                    print(f"   [SKIP] Target {target} falló en todas las cuentas.")
                    break
            else:
                target_fail_count = 0

            if current_leads >= MAX_LEADS_PER_TARGET: break
            if success: break 
            
            scraper_acc_index += 1
            time.sleep(2)

if __name__ == "__main__":
    main()