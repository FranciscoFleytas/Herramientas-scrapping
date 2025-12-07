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

# --- CONFIGURACIÓN ---
TARGET_PROFILES = ["doctorsterling", "integrativepeptides","dave.asprey","m2bwellness","nutritionandwellnessguy","drseandrake","thesoulhakker"]  
MAX_LEADS_PER_TARGET = 300      
MIN_FOLLOWERS = 100000      
MAX_FOLLOWERS_CAP = 450000 
MIN_POSTS = 100           
MAX_ENGAGEMENT_THRESHOLD = 3.0 
MAX_CONSECUTIVE_EMPTY_SCROLLS = 15 
SAFETY_SESSION_LIMIT = 30

# PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# --- MAPEO DE NICHOS EXTENDIDO (ANÁLISIS DE MERCADO) ---
NICHE_MAPPING = {
    "Salud & Medicina": [
        "medico", "doctor", "medic", "surgeon", "cirujano", "plastic surgeon", "cirujano plastico",
        "dermatologist", "dermatologo", "dentist", "dentista", "odontologo", "aesthetician", 
        "esteticista", "injector", "botox", "psychologist", "psicologo", "therapist", "terapeuta",
        "nutritionist", "nutricionista", "dietitian", "dietista", "chiropractor", "quiropractico",
        "physiotherapist", "fisioterapeuta", "md", "phd", "clinic owner", "dueño de clinica",
        "wellness", "bienestar", "mental health", "salud mental", "holistic", "holistico",
        "pediatrician", "pediatra", "cardiologist", "cardiologo", "neurologist", "neurologo"
    ],
    "Real Estate & Arquitectura": [
        "real estate", "bienes raices", "inmobiliaria", "realtor", "architect", "arquitecto",
        "interior design", "diseñador de interiores", "urbanizeproperties", "property", "propiedades",
        "broker", "corredor", "construction", "construccion", "developer", "desarrollador",
        "home staging", "luxury homes", "casas de lujo"
    ],
    "Negocios & Emprendimiento": [
        "ceo", "founder", "fundador", "business owner", "dueño de negocio", "entrepreneur", 
        "emprendedor", "consultant", "consultor", "agency owner", "dueño de agencia",
        "startup", "co-founder", "co-fundador", "president", "presidente", "director", 
        "manager", "gerente", "executive", "ejecutivo", "boss", "leader", "lider",
        "management", "gestion", "solutions", "soluciones"
    ],
    "Marketing & Ventas": [
        "marketing", "marketer", "sales", "ventas", "closer", "high ticket", "sales trainer",
        "strategist", "estratega", "brand specialist", "branding", "copywriter", "redactor", 
        "seo", "media buyer", "trafficker", "trafico", "social media manager", "community manager", 
        "smm", "smma", "growth hacker", "pr", "public relations", "relaciones publicas",
        "digital marketing", "marketing digital", "advertising", "publicidad", "ads"
    ],
    "Finanzas & Inversiones": [
        "investor", "inversor", "trader", "trading", "crypto", "blockchain", "financial advisor", 
        "asesor financiero", "finance", "finanzas", "accountant", "contador", "cpa", "tax", 
        "impuestos", "wealth management", "gestion de patrimonio", "bitcoin", "forex", 
        "stock market", "bolsa", "economist", "economista", "capital", "venture"
    ],
    "Educación & Coaching": [
        "coach", "mentor", "mentoring", "teacher", "profesor", "educator", "educador",
        "trainer", "entrenador", "tutor", "academy", "academia", "course", "curso",
        "masterclass", "speaker", "conferencista", "public speaker", "author", "autor"
    ],
    "Creadores & Influencers": [
        "influencer", "creator", "creador", "podcast", "ugc", "ugc creator",
        "infoproducer", "infoproductor", "blogger", "vlogger", "youtuber", "streamer", 
        "tiktok", "content", "contenido", "ambassador", "embajador"
    ],
    "Moda & Belleza": [
        "model", "modelo", "fashion", "moda", "stylist", "estilista", "makeup artist", 
        "maquilladora", "mua", "hair", "barber", "barbero", "beauty", "belleza", 
        "skincare", "piel", "salon", "boutique", "clothing", "ropa", "jewelry", "joyeria"
    ],
    "Arte & Creatividad": [
        "photographer", "fotografo", "videographer", "filmmaker", "editor", "video editor", 
        "art director", "director de arte", "graphic designer", "diseñador grafico", 
        "artist", "artista", "writer", "escritor", "journalist", "periodista", 
        "dj", "producer", "productor", "music", "musica", "musician", "musico",
        "illustrator", "ilustrador", "painter", "pintor", "gallery", "galeria"
    ],
    "Tecnología & Software": [
        "tech", "tecnologia", "saas", "software", "app developer", "desarrollador", 
        "cto", "cmo", "coo", "vp", "engineer", "ingeniero", "web3", "ai", 
        "artificial intelligence", "data", "datos", "programmer", "programador", "it"
    ],
    "Lifestyle, Fitness & Food": [
        "fitness", "gym", "gimnasio", "personal trainer", "yoga", "pilates", "athlete", "atleta",
        "chef", "gastronomy", "gastronomia", "restaurant owner", "dueño de restaurante",
        "foodie", "travel", "viajes", "luxury", "lujo", "event planner", "organizador de eventos",
        "mom", "mama", "dad", "papa", "lifestyle", "estilo de vida"
    ]
}

# --- GESTIÓN DE RUTAS Y CARPETAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')
RESULTS_DIR = os.path.join(SCRIPT_DIR, "RESULTADOS")

if not os.path.exists(RESULTS_DIR):
    try: os.makedirs(RESULTS_DIR)
    except OSError: pass

# --- ARCHIVOS GLOBALES ---
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
    """
    Busca palabras clave en la descripción y retorna el NOMBRE DEL NICHO UNIFICADO.
    """
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
    try:
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/p/')]"))
            )
        except:
            return 0.0

        links_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
        all_hrefs = []
        seen = set()
        for elem in links_elements:
            h = elem.get_attribute('href')
            if h and h not in seen:
                all_hrefs.append(h)
                seen.add(h)

        if len(all_hrefs) < 4:
            return 0.0

        target_urls = all_hrefs[3:8] 
        
        if not target_urls:
            return 0.0

        total_interactions = 0
        posts_analyzed = 0

        for url in target_urls:
            try:
                driver.get(url)
                if "login" in driver.current_url:
                    print(" [!] Redirigido a Login al analizar post.")
                    break

                meta = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//meta[@name='description']"))
                )
                content = meta.get_attribute("content")
                
                likes = 0
                comments = 0
                
                l_match = re.search(r'([0-9\.,kmKM]+)\s*(likes|me gusta)', content, re.IGNORECASE)
                c_match = re.search(r'([0-9\.,kmKM]+)\s*(comments|comentarios)', content, re.IGNORECASE)
                
                if l_match: likes = parse_social_number(l_match.group(1))
                if c_match: comments = parse_social_number(c_match.group(1))
                
                total = likes + comments
                total_interactions += total
                posts_analyzed += 1
                
                time.sleep(random.uniform(1.0, 1.5))
                
            except Exception:
                pass 

        if posts_analyzed == 0 or followers == 0:
            return 0.0

        avg_interactions = total_interactions / posts_analyzed
        engagement_rate = (avg_interactions / followers) * 100
        
        return round(engagement_rate, 2)

    except Exception as e:
        print(f"   [ERR ENG] {e}")
        return 0.0

def analyze_profile_visual(driver, username):
    try:
        wait = WebDriverWait(driver, 10)
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

        category = extract_category(driver)
        niche = get_niche_match(meta_content)

        if not (MIN_FOLLOWERS <= followers <= MAX_FOLLOWERS_CAP):
            print(f"   [X] Followers: {followers}")
            return False, followers, posts, category, niche, 0
        
        if posts < MIN_POSTS:
            print(f"   [X] Inactivo ({posts} posts)")
            return False, followers, posts, category, niche, 0
            
        engagement = calculate_real_engagement(driver, followers)
        
        if engagement >= MAX_ENGAGEMENT_THRESHOLD:
            print(f"   [X] High Eng: {engagement}% (Limit: <{MAX_ENGAGEMENT_THRESHOLD}%)")
            return False, followers, posts, category, niche, engagement

        print(f"   [OK] LEAD: {username} | F:{followers} | Eng:{engagement}% | Nicho:{niche}")
        return True, followers, posts, category, niche, engagement

    except: return False, 0, 0, "-", "-", 0

def run_scraper_session(account, current_leads_count, target_profile):
    if not account.get('sessionid'): return False, 0
    
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
            print("[ERROR] No se pudo abrir la lista (Cuenta privada o oculta).")
            return False, 0

        time.sleep(3)
        
        analyzed_history = load_global_history()
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
                save_to_global_history(user)

                try:
                    driver.execute_script("window.open('about:blank', '_blank');")
                    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(f"https://www.instagram.com/{user}/")
                    
                    is_valid, num_f, num_p, cat, niche, eng_rate = analyze_profile_visual(driver, user)
                    
                    driver.close()
                    driver.switch_to.window(main_window)
                    
                    if is_valid:
                        leads_added_this_session += 1
                        total_now = current_leads_count + leads_added_this_session
                        
                        print(f"   >>> [PROGRESO] {total_now}/{MAX_LEADS_PER_TARGET} Leads para {target_profile}")
                        
                        with open(SESSION_CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f:
                            writer = csv.writer(f, delimiter=';')
                            writer.writerow([user, f"https://instagram.com/{user}", num_f, num_p, cat, niche, f"{eng_rate}%", target_profile])
                        
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
    print(f"--- SCRAPER MULTI-TARGET (SESIÓN UNICA) ---")
    print(f"--- Archivo de sesión: {os.path.basename(SESSION_CSV_FILE)} ---")
    
    accounts = load_accounts()
    if not accounts: return

    with open(SESSION_CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["Usuario", "URL", "Seguidores", "Publicaciones", "Categoria", "Nicho", "Engagement", "Origen"])

    scraper_acc_index = 0

    for target in TARGET_PROFILES:
        current_leads = get_current_leads_count_global(target)
        print(f"\n>>> PROCESANDO TARGET: {target} | Leads históricos totales: {current_leads}/{MAX_LEADS_PER_TARGET}")

        if current_leads >= MAX_LEADS_PER_TARGET: 
            print("   Objetivo ya completado anteriormente. Saltando.")
            continue
        
        target_fail_count = 0

        while current_leads < MAX_LEADS_PER_TARGET:
            if scraper_acc_index >= len(accounts):
                print("Ciclo de cuentas terminado. Esperando 5 min...")
                time.sleep(300)
                scraper_acc_index = 0
            
            current_acc = accounts[scraper_acc_index]
            success, leads_found_session = run_scraper_session(current_acc, current_leads, target)
            current_leads += leads_found_session
            
            if not success and leads_found_session == 0:
                target_fail_count += 1
                if target_fail_count >= len(accounts):
                    print(f"   [SKIP] El target {target} falló con todas las cuentas disponibles. Saltando al siguiente.")
                    break
            else:
                target_fail_count = 0

            if current_leads >= MAX_LEADS_PER_TARGET: break
            
            if success:
                print(f"   Target {target} finalizado (objetivo alcanzado o lista agotada).")
                break 
            
            scraper_acc_index += 1
            print(f"   Cambiando cuenta de scraping (mismo Target)...")
            time.sleep(5)

if __name__ == "__main__":
    main()