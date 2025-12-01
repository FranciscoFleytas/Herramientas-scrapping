import time
import csv
import os
import threading
import queue
import hashlib 
import random
import requests
from concurrent.futures import ThreadPoolExecutor
from itertools import islice, cycle 
import urllib3
import instaloader

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CREDENCIALES BRIGHT DATA ---
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER_BASE = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar" 
PROXY_PASS = "ei0g975bijby"

# --- CONFIGURACION DE SEGURIDAD ---
USER_AGENTS_MAPPING = {
    "fabiangoltra44": "Instagram 219.0.0.12.117 Android (31/12; 480dpi; 1080x2400; Xiaomi; M2007J20CG; surya; qcom; en_US; 368526978)",
    "franciflee": "Instagram 265.0.0.19.301 iPhone14,2; iOS 16.1; en_US; en-US; scale=3.00; 1170x2532; 418526978"
}
DEFAULT_UA = "Instagram 200.0.0.30.120 Android (29/10; 420dpi; 1080x2130; Google/google; pixel 4; qcom; en_US; 320922800)"

# --- CONFIGURACION DE PRODUCCION ---
TEST_MODE_SAVE_ALL = False
TARGET_PROFILE = "imthatquez" 
MIN_FOLLOWERS = 2000    
MIN_POSTS = 20         
ENGAGEMENT_THRESHOLD = 0.03
BAD_POSTS_PERCENTAGE = 0.60 
POSTS_TO_CHECK = 10      
WORKERS_PER_ACCOUNT = 1

# --- RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Optimización: Detección universal del escritorio (Win/Mac/Linux)
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")

CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.txt')
# Archivo para recordar usuarios ya analizados (Guardados + Descartados)
HISTORY_FILE = os.path.join(SCRIPT_DIR, f'history_{TARGET_PROFILE}.txt')
CSV_FILENAME = os.path.join(DESKTOP_DIR, f'leads_{TARGET_PROFILE}.csv')
SESSION_DIR = SCRIPT_DIR
PROXY_COUNTRIES = ['us']

# --- GLOBALES ---
STATS_LOCK = threading.Lock()
POOL_LOCK = threading.Lock() 
SESSION_OBJECTS = {} 
ACCOUNTS_POOL = [] 
BANNED_ACCOUNTS = set()
VISITED_USERS = set() # Set en memoria para O(1) lookup
WRITE_QUEUE = queue.Queue()
PROCESSED_COUNT = 0
SAVED_COUNT = 0

def load_accounts_from_txt():
    if not os.path.exists(CUENTAS_FILE):
        print(f"[ERROR] No se encontró 'cuentas.txt' en: {SCRIPT_DIR}")
        return {}, []
    
    accounts_data = {}
    accounts_list = []
    
    with open(CUENTAS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if ':' in line:
                parts = line.split(':')
                user = parts[0].strip()
                pwd = parts[1].strip()
                backup_code = parts[2].strip() if len(parts) > 2 else None
                accounts_data[user] = {'pass': pwd, 'backup_code': backup_code}
                accounts_list.append(user)
    return accounts_data, accounts_list

# --- GESTION DE HISTORIAL ---
def load_history():
    """Carga usuarios ya analizados para no repetir trabajo."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                VISITED_USERS.add(line.strip())
        print(f"Historial cargado: {len(VISITED_USERS)} usuarios ya ignorados.")

def save_visit_async(username):
    """Guarda usuario en historial sin bloquear el hilo principal."""
    try:
        with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{username}\n")
    except: pass

class CSVWriterThread(threading.Thread):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            try:
                if WRITE_QUEUE.empty():
                    time.sleep(0.5)
                    continue

                mode = 'a' if os.path.exists(self.filename) else 'w'
                with open(self.filename, mode, newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';')
                    if mode == 'w':
                        writer.writerow(["Usuario", "URL", "Seguidores", "Posts Analizados", "Posts Malos", "Ratio Fallo"])
                    
                    count = 0
                    while not WRITE_QUEUE.empty() and count < 50:
                        data = WRITE_QUEUE.get()
                        if data:
                            writer.writerow(data)
                            WRITE_QUEUE.task_done()
                            count += 1
                    f.flush()
                    os.fsync(f.fileno()) 
            except PermissionError:
                print(f"[ERROR] Cierra el CSV para guardar datos.")
                time.sleep(2)
            except Exception:
                time.sleep(1)

    def stop(self):
        self.running = False

def check_proxy_connection(proxy_url):
    try:
        proxies = {'http': proxy_url, 'https': proxy_url}
        requests.get("https://lumtest.com/myip.json", proxies=proxies, timeout=10, verify=False)
        return True
    except Exception:
        return False

def init_session(username, account_details):
    if username in BANNED_ACCOUNTS: return None
    
    password = account_details['pass']
    backup_code_static = account_details['backup_code']
    my_ua = USER_AGENTS_MAPPING.get(username, DEFAULT_UA)

    BASE_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

    for attempt in range(4):
        session_id = str(random.randint(10000000, 99999999))
        country_code = PROXY_COUNTRIES[attempt % len(PROXY_COUNTRIES)]
        proxy_user_full = f"{PROXY_USER_BASE}-country-{country_code}-session-{session_id}"
        proxy_url = f"http://{proxy_user_full}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        
        print(f"[{username}] IP: {country_code.upper()}... ", end="")

        if not check_proxy_connection(proxy_url):
            print("X")
            continue
        print("OK.")

        L = instaloader.Instaloader(
            sleep=True, 
            user_agent=my_ua,
            max_connection_attempts=1,
            request_timeout=30,
            fatal_status_codes=[400, 401, 429, 403]
        )
        
        L.context._session.proxies = {'http': proxy_url, 'https': proxy_url}
        L.context._session.verify = False 
        L.context._session.headers.update(BASE_HEADERS)
        L.context._session.headers.update({"User-Agent": my_ua})

        session_file = os.path.join(SESSION_DIR, f"{username}.session")

        try:
            if os.path.exists(session_file) and attempt == 0:
                try:
                    L.load_session_from_file(username, filename=session_file)
                    print(f"[{username}] Sesión cargada.")
                    return L
                except:
                    print(f"[{username}] Sesión inválida.")

            try: L.context._session.get("https://www.instagram.com/", timeout=15)
            except: pass

            try:
                L.login(username, password)
            except instaloader.TwoFactorAuthRequiredException:
                print(f"\n[2FA] {username}")
                code_to_use = backup_code_static if backup_code_static else input(f">> Código: ").strip()
                try:
                    L.context.two_factor_login(code_to_use)
                    L.save_session_to_file(filename=session_file)
                    print(f"[{username}] 2FA OK.")
                    return L
                except Exception:
                    return None

            L.save_session_to_file(filename=session_file)
            print(f"[{username}] Login OK.")
            return L

        except Exception:
            time.sleep(1)
            continue
    return None

def check_engagement_logic(L, profile):
    try:
        posts = list(islice(profile.get_posts(), POSTS_TO_CHECK))
    except Exception:
        return False, 0, 0
    
    # Optimización: Evitar división por cero
    if not posts or len(posts) == 0: 
        return False, 0, 0

    min_likes = profile.followers * ENGAGEMENT_THRESHOLD
    bad_posts = sum(1 for p in posts if p.likes < min_likes)
    return (bad_posts / len(posts)) >= BAD_POSTS_PERCENTAGE, bad_posts, (bad_posts / len(posts))

def kill_account(username):
    with POOL_LOCK:
        if username in ACCOUNTS_POOL:
            ACCOUNTS_POOL.remove(username)
    if username in SESSION_OBJECTS:
        del SESSION_OBJECTS[username]

def worker_task(target_user, account_user):
    global PROCESSED_COUNT, SAVED_COUNT
    
    if account_user not in SESSION_OBJECTS: return
    L = SESSION_OBJECTS[account_user]

    try:
        time.sleep(random.uniform(1.0, 3.0)) 

        profile = instaloader.Profile.from_username(L.context, target_user)
        
        if profile.is_private: return
        if profile.followers < MIN_FOLLOWERS: return
        if profile.mediacount < MIN_POSTS: return

        is_lead, bad_count, ratio = check_engagement_logic(L, profile)

        should_save = is_lead or TEST_MODE_SAVE_ALL 
        
        if should_save:
            status_msg = "GUARDADO"
        else:
            status_msg = f"DESCARTADO ({bad_count}/{POSTS_TO_CHECK})"
        
        with STATS_LOCK:
            PROCESSED_COUNT += 1
            print(f"[{PROCESSED_COUNT}|{SAVED_COUNT}] {target_user:<15} | Ratio: {ratio:.2f} | {status_msg}", end='\r')

        # Guardamos en historial SIEMPRE, sea bueno o malo
        VISITED_USERS.add(target_user)
        save_visit_async(target_user)

        if should_save:
            url = f"https://instagram.com/{target_user}"
            WRITE_QUEUE.put([target_user, url, profile.followers, POSTS_TO_CHECK, bad_count, f"{ratio:.2f}"])
            with STATS_LOCK: SAVED_COUNT += 1

    except Exception as e:
        err = str(e)
        if "401" in err or "429" in err or "login" in err.lower():
            kill_account(account_user)

def main():
    global ACCOUNTS_POOL
    load_history() # Carga previa de historial
    
    ACCOUNTS_DATA, raw_accounts = load_accounts_from_txt()
    if not raw_accounts: return

    print(f"--- Cargando {len(raw_accounts)} cuentas ---")
    
    for acc in raw_accounts:
        l_instance = init_session(acc, ACCOUNTS_DATA[acc])
        if l_instance:
            SESSION_OBJECTS[acc] = l_instance
            ACCOUNTS_POOL.append(acc)
            time.sleep(2)
    
    if not ACCOUNTS_POOL: 
        print("\n[ERROR] Sin cuentas activas.")
        return

    total_workers = len(ACCOUNTS_POOL) * WORKERS_PER_ACCOUNT
    print(f"\n>>> INICIANDO SCRAPING ({total_workers} Workers) <<<")

    writer_thread = CSVWriterThread(CSV_FILENAME)
    writer_thread.start()

    pool_cycle = cycle(ACCOUNTS_POOL)
    followers_iter = None
    
    for candidate in list(ACCOUNTS_POOL):
        try:
            L_candidate = SESSION_OBJECTS[candidate]
            target = instaloader.Profile.from_username(L_candidate.context, TARGET_PROFILE)
            followers_iter = target.get_followers()
            print(f"Maestro: {candidate} -> Target: {TARGET_PROFILE} ({target.followers} followers)")
            break 
        except:
            kill_account(candidate)

    if not followers_iter: return

    try:
        with ThreadPoolExecutor(max_workers=total_workers) as executor:
            while True:
                with POOL_LOCK:
                    if not ACCOUNTS_POOL: break
                    worker_acc = next(pool_cycle)
                    while worker_acc not in SESSION_OBJECTS:
                        worker_acc = next(pool_cycle)
                        if not ACCOUNTS_POOL: break

                try:
                    follower = next(followers_iter)
                    
                    # VALIDACION DE HISTORIAL
                    if follower.username in VISITED_USERS: 
                        continue
                    
                    executor.submit(worker_task, follower.username, worker_acc)
                    time.sleep(random.uniform(0.5, 2.0))

                except StopIteration:
                    break
                except Exception:
                    time.sleep(5)
                    
    except KeyboardInterrupt:
        print("\nDeteniendo...")
    finally:
        writer_thread.stop()
        print(f"\nFinalizado. CSV en: {CSV_FILENAME}")
        print(f"Historial actualizado en: {HISTORY_FILE}")

if __name__ == "__main__":
    main()