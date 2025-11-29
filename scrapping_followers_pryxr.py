import time
import csv
import os
import threading
import queue
import hashlib 
import random
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
import urllib3
import instaloader

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CREDENCIALES BRIGHT DATA (ARGENTINA) ---
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER_BASE = "brd-customer-hl_23e53168-zone-scrapping_usser-country-ar"
PROXY_PASS = "6p7y5qv5mz4q"

# --- CONFIGURACION DE SCRAPING ---
TARGET_PROFILE = "rkcoaching__"
MIN_FOLLOWERS = 100
MIN_POSTS = 3
ENGAGEMENT_THRESHOLD = 0.03
BAD_POSTS_PERCENTAGE = 0.7
POSTS_TO_CHECK = 10
WORKERS_PER_ACCOUNT = 1  # MÁXIMO SEGURO: 2. Si subes a 3, riesgo alto.

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
SESSION_OBJECTS = {} 
BANNED_ACCOUNTS = set()
SAVED_USERS = set()
WRITE_QUEUE = queue.Queue()
PROCESSED_COUNT = 0
SAVED_COUNT = 0

def load_accounts_from_txt():
    """Lee cuentas.txt y retorna lista y diccionario."""
    if not os.path.exists(CUENTAS_FILE):
        print(f"ERROR: No se encontró {CUENTAS_FILE}")
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

def init_session(username, password):
    if username in BANNED_ACCOUNTS: return None

    L = instaloader.Instaloader(
        sleep=True,
        user_agent="Instagram 200.0.0.30.120 Android (29/10; 420dpi; 1080x2130; Google/google; pixel 4; qcom; en_US; 320922800)",
        max_connection_attempts=3,
        request_timeout=30
    )

    # Lógica Sticky IP Escalable: Cada usuario del TXT tendrá su propia IP única
    session_id = hashlib.md5(username.encode()).hexdigest()[:8]
    proxy_user_full = f"{PROXY_USER_BASE}-session-{session_id}"
    proxy_url = f"http://{proxy_user_full}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    
    L.context._session.proxies = {'http': proxy_url, 'https': proxy_url}
    L.context._session.verify = False 

    session_file = os.path.join(SESSION_DIR, f"{username}.session")
    
    try:
        # Prioridad: Cargar sesión existente
        if os.path.exists(session_file):
            L.load_session_from_file(username, filename=session_file)
            print(f"[{username}] Sesión OK.")
        else:
            # Fallback: Login con password del TXT
            print(f"[{username}] Creando nueva sesión...")
            L.login(username, password)
            L.save_session_to_file(filename=session_file)
            print(f"[{username}] Login OK.")
    except Exception as e:
        print(f"[{username}] FALLO: {e}")
        return None

    return L

def check_engagement_logic(L, profile):
    try:
        posts = list(islice(profile.get_posts(), POSTS_TO_CHECK))
    except Exception:
        return False, 0, 0
    
    if not posts: return False, 0, 0

    min_likes = profile.followers * ENGAGEMENT_THRESHOLD
    bad_posts = sum(1 for p in posts if p.likes < min_likes)
    return (bad_posts / len(posts)) >= BAD_POSTS_PERCENTAGE, bad_posts, (bad_posts / len(posts))

def worker_task(target_user, account_user):
    global PROCESSED_COUNT, SAVED_COUNT
    L = SESSION_OBJECTS.get(account_user)
    if not L: return

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
        # MODIFICACION: Si es 401/Wait, matamos la cuenta en esta ejecución
        if "401" in err or "429" in err or "wait" in err.lower() or "login" in err.lower():
            print(f"\n[CRITICO] Cuenta {account_user} BLOQUEADA (401). Eliminando del pool...")
            # Eliminamos la sesión de la memoria para que no se use más
            if account_user in SESSION_OBJECTS:
                del SESSION_OBJECTS[account_user]
            return # Salir inmediatamente

def main():
    load_existing_db()
    
    # 1. Cargar Cuentas
    ACCOUNTS_DATA, ACCOUNTS_POOL = load_accounts_from_txt()
    if not ACCOUNTS_POOL:
        print("ERROR: Crea el archivo 'cuentas.txt' con formato usuario:pass")
        return

    print(f"--- Cargando {len(ACCOUNTS_POOL)} cuentas ---")
    
    valid_pool = []
    for acc in ACCOUNTS_POOL:
        l_instance = init_session(acc, ACCOUNTS_DATA[acc])
        if l_instance:
            SESSION_OBJECTS[acc] = l_instance
            valid_pool.append(acc)
    
    ACCOUNTS_POOL = valid_pool
    if not ACCOUNTS_POOL: return

    # 2. Calcular Workers
    total_workers = len(ACCOUNTS_POOL) * WORKERS_PER_ACCOUNT
    print(f"\n>>> INICIANDO CON {total_workers} WORKERS ({WORKERS_PER_ACCOUNT} por cuenta) <<<")

    writer_thread = CSVWriterThread(CSV_FILENAME)
    writer_thread.start()

    master_acc = ACCOUNTS_POOL[0]
    try:
        L_master = SESSION_OBJECTS[master_acc]
        target = instaloader.Profile.from_username(L_master.context, TARGET_PROFILE)
        followers_iter = target.get_followers()
        
        with ThreadPoolExecutor(max_workers=total_workers) as executor:
            while True:
                try:
                    follower = next(followers_iter)
                    if follower.username in SAVED_USERS: continue
                    
                    # Round Robin mejorado para distribuir carga
                    worker_acc = random.choice(ACCOUNTS_POOL)
                    executor.submit(worker_task, follower.username, worker_acc)
                    
                    # Ritmo de inyección de tareas (ajustar según cantidad de workers)
                    time.sleep(0.01 if total_workers > 10 else 0.1)

                except StopIteration:
                    break
                except Exception as e:
                    print(f"\n[Master Error] {e} - Pausando...")
                    time.sleep(30)
                    
    except KeyboardInterrupt:
        print("\nDeteniendo...")
    finally:
        writer_thread.stop()
        print("Finalizado.")

if __name__ == "__main__":
    main()