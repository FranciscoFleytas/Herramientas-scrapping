import time
import csv
import os
import threading
import queue
import random
import requests
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
import urllib3
import instaloader

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CREDENCIALES BRIGHT DATA ---
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER_BASE = "brd-customer-hl_23e53168-zone-scrapping_usser-country-ar"
PROXY_PASS = "6p7y5qv5mz4q"

# --- CONFIGURACION ---
TARGET_PROFILE = "rkcoaching__"
MIN_FOLLOWERS = 100
MIN_POSTS = 3
ENGAGEMENT_THRESHOLD = 0.03
BAD_POSTS_PERCENTAGE = 0.7
POSTS_TO_CHECK = 10
WORKERS_PER_ACCOUNT = 1 

# --- RUTAS ---
try:
    desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
except:
    desktop = os.getcwd()

CUENTAS_FILE = os.path.join(desktop, 'cuentas.txt')
CSV_FILENAME = os.path.join(desktop, f'leads_bajo_engagement_{TARGET_PROFILE}.csv')
SESSION_DIR = desktop 

# --- GLOBALES ---
STATS_LOCK = threading.Lock()
POOL_LOCK = threading.Lock() 
SESSION_OBJECTS = {} 
ACCOUNTS_POOL = [] 
BANNED_ACCOUNTS = set()
SAVED_USERS = set()
WRITE_QUEUE = queue.Queue()
PROCESSED_COUNT = 0
SAVED_COUNT = 0

def load_accounts_from_txt():
    if not os.path.exists(CUENTAS_FILE):
        print(f"[ERROR] No se encontro {CUENTAS_FILE}")
        return {}, []
    
    accounts_data = {}
    accounts_list = []
    
    with open(CUENTAS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if ':' in line:
                user, pwd = line.split(':', 1)
                accounts_data[user.strip()] = pwd.strip()
                accounts_list.append(user.strip())
    return accounts_data, accounts_list

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
                    time.sleep(1)
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
                            SAVED_USERS.add(data[0])
                            WRITE_QUEUE.task_done()
                            count += 1
                    f.flush()
                    os.fsync(f.fileno())
            except PermissionError:
                print(f"[ERROR] Excel abierto. Cerrar para guardar.")
                time.sleep(5)
            except Exception:
                time.sleep(1)

    def stop(self):
        self.running = False

def load_existing_db():
    global SAVED_COUNT
    if os.path.exists(CSV_FILENAME):
        try:
            with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=';')
                next(reader, None)
                for row in reader:
                    if row: SAVED_USERS.add(row[0])
            SAVED_COUNT = len(SAVED_USERS)
            print(f"Base de datos precargada: {SAVED_COUNT} registros.")
        except Exception:
            pass

# --- VALIDACION DE RED ---
def check_proxy_connection(proxy_url):
    """Prueba simple de conectividad a Bright Data."""
    try:
        proxies = {'http': proxy_url, 'https': proxy_url}
        # Timeout estricto de 8s
        requests.get("http://lumtest.com/myip.json", proxies=proxies, timeout=8, verify=False)
        return True
    except:
        return False

# --- LOGICA DE INICIO SIMPLIFICADA (IP FRESCA SIEMPRE) ---
def init_session(username, password):
    if username in BANNED_ACCOUNTS: return None

    # Intentamos hasta 3 IPs aleatorias diferentes
    for attempt in range(3):
        
        # SIEMPRE generamos una session ID nueva (IP Fresca)
        session_id = str(random.randint(10000000, 99999999))
        proxy_user_full = f"{PROXY_USER_BASE}-session-{session_id}"
        proxy_url = f"http://{proxy_user_full}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        
        print(f"[{username}] Probando IP Aleatoria ({session_id})...", end=" ")

        if not check_proxy_connection(proxy_url):
            print("FALLO RED. Reintentando...")
            continue # Siguiente IP

        print("RED OK. Conectando...")

        L = instaloader.Instaloader(
            sleep=True,
            user_agent="Instagram 200.0.0.30.120 Android (29/10; 420dpi; 1080x2130; Google/google; pixel 4; qcom; en_US; 320922800)",
            max_connection_attempts=1,
            request_timeout=30,
            fatal_status_codes=[400, 401, 429, 403]
        )
        
        L.context._session.proxies = {'http': proxy_url, 'https': proxy_url}
        L.context._session.verify = False 

        session_file = os.path.join(SESSION_DIR, f"{username}.session")

        try:
            # Intentar cargar sesion guardada PRIMERO
            # Nota: Al cambiar de IP, la sesion puede invalidarse, pero vale la pena intentar.
            if os.path.exists(session_file) and attempt == 0:
                try:
                    L.load_session_from_file(username, filename=session_file)
                    print(f"[{username}] Sesion cargada de disco.")
                    return L
                except:
                    print(f"[{username}] Archivo sesion invalido.")

            # Si no hay sesion o fallo carga, LOGIN desde cero
            try:
                # Pre-fetch cookies
                L.context.get_json("https://www.instagram.com/data/shared_data/")
            except: pass 

            try:
                L.login(username, password)
            except instaloader.TwoFactorAuthRequiredException:
                print(f"\n[2FA REQUERIDO] {username}")
                print(f"IP: {session_id}")
                
                while True:
                    code = input(f">> Codigo 2FA para {username}: ").strip()
                    if not code: continue
                    
                    try:
                        L.context.two_factor_login(code)
                        L.save_session_to_file(filename=session_file)
                        print(f"[{username}] 2FA Exitoso.")
                        return L
                    except Exception as e:
                        if "Expecting value" in str(e) or "JSON" in str(e):
                            raise Exception("Fallo Proxy 2FA")
                        print(f"[ERROR] Codigo incorrecto: {e}")
                        if input("Reintentar? (s/n): ").lower() != 's': return None

            L.save_session_to_file(filename=session_file)
            print(f"[{username}] Login OK.")
            return L

        except Exception as e:
            print(f"[{username}] Error intento {attempt+1}: {e}")
            time.sleep(2)
            continue

    print(f"[{username}] Imposible conectar tras 3 intentos.")
    return None

def check_engagement_logic(L, profile):
    try:
        posts = list(islice(profile.get_posts(), POSTS_TO_CHECK))
    except Exception:
        return False, 0, 0
    
    if not posts: return False, 0, 0

    min_likes = profile.followers * ENGAGEMENT_THRESHOLD
    bad_posts = sum(1 for p in posts if p.likes < min_likes)
    return (bad_posts / len(posts)) >= BAD_POSTS_PERCENTAGE, bad_posts, (bad_posts / len(posts))

def kill_account(username):
    with POOL_LOCK:
        if username in ACCOUNTS_POOL:
            ACCOUNTS_POOL.remove(username)
            print(f"\n[SISTEMA] CUENTA ELIMINADA: {username}")
    if username in SESSION_OBJECTS:
        del SESSION_OBJECTS[username]

def worker_task(target_user, account_user):
    global PROCESSED_COUNT, SAVED_COUNT
    
    if account_user not in SESSION_OBJECTS: return
    L = SESSION_OBJECTS[account_user]

    try:
        profile = instaloader.Profile.from_username(L.context, target_user)
        if profile.is_private or profile.followers < MIN_FOLLOWERS: return

        is_lead, bad_count, ratio = check_engagement_logic(L, profile)

        with STATS_LOCK:
            PROCESSED_COUNT += 1
            print(f"[{PROCESSED_COUNT}|{SAVED_COUNT}] {target_user:<15} | Ratio: {ratio:.2f}", end='\r')

        if is_lead:
            url = f"https://instagram.com/{target_user}"
            WRITE_QUEUE.put([target_user, url, profile.followers, POSTS_TO_CHECK, bad_count, f"{ratio:.2f}"])
            with STATS_LOCK: SAVED_COUNT += 1

    except (instaloader.ConnectionException, instaloader.LoginRequiredException, instaloader.QueryReturnedBadRequestException) as e:
        err = str(e)
        if "401" in err or "429" in err or "wait" in err.lower() or "login" in err.lower() or "403" in err:
            kill_account(account_user)
            return 

def main():
    global ACCOUNTS_POOL
    load_existing_db()
    
    ACCOUNTS_DATA, raw_accounts = load_accounts_from_txt()
    if not raw_accounts:
        print("[ERROR] Crea 'cuentas.txt'")
        return

    print(f"--- Cargando {len(raw_accounts)} cuentas ---")
    
    for acc in raw_accounts:
        l_instance = init_session(acc, ACCOUNTS_DATA[acc])
        if l_instance:
            SESSION_OBJECTS[acc] = l_instance
            ACCOUNTS_POOL.append(acc)
    
    if not ACCOUNTS_POOL: 
        print("\n[ERROR FATAL] Ninguna cuenta pudo conectarse.")
        return

    total_workers = len(ACCOUNTS_POOL) * WORKERS_PER_ACCOUNT
    print(f"\n>>> INICIANDO CON {total_workers} WORKERS <<<")

    writer_thread = CSVWriterThread(CSV_FILENAME)
    writer_thread.start()

    followers_iter = None
    candidates_copy = list(ACCOUNTS_POOL)

    for candidate_master in candidates_copy:
        try:
            print(f"Probando MAESTRO: {candidate_master}...", end=" ")
            L_candidate = SESSION_OBJECTS[candidate_master]
            target_profile_obj = instaloader.Profile.from_username(L_candidate.context, TARGET_PROFILE)
            _ = target_profile_obj.userid 
            followers_iter = target_profile_obj.get_followers()
            print(f"OK. ({target_profile_obj.followers} seguidores)")
            break 
        except Exception as e:
            print(f"FALLO ({e}). Eliminando...")
            kill_account(candidate_master)

    if followers_iter is None:
        print("\n[CRITICO] Todas las cuentas fallaron.")
        writer_thread.stop()
        return

    try:
        with ThreadPoolExecutor(max_workers=total_workers) as executor:
            while True:
                with POOL_LOCK:
                    if not ACCOUNTS_POOL:
                        print("\n\n[SISTEMA] TODAS LAS CUENTAS MURIERON.")
                        break
                    current_pool = list(ACCOUNTS_POOL)

                try:
                    follower = next(followers_iter)
                    if follower.username in SAVED_USERS: continue
                    
                    worker_acc = random.choice(current_pool)
                    executor.submit(worker_task, follower.username, worker_acc)
                    time.sleep(0.1)

                except StopIteration:
                    print("\n--- Fin de lista ---")
                    break
                except Exception as e:
                    print(f"\n[Error Maestro] {e}")
                    break
                    
    except KeyboardInterrupt:
        print("\nDeteniendo...")
    finally:
        writer_thread.stop()
        print("Finalizado.")

if __name__ == "__main__":
    main()