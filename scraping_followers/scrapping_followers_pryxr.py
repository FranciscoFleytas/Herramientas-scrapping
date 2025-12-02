import time
import csv
import os
import threading
import queue
import hashlib 
import random
import requests
from concurrent.futures import ThreadPoolExecutor
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

# --- CONFIGURACION DE FILTRADO ---
TARGET_PROFILE = "mickunplugged" 

# RANGO DE SEGUIDORES (NUEVO)
MIN_FOLLOWERS = 2000    # Mínimo de seguidores
MAX_FOLLOWERS = 100000  # Máximo de seguidores

MIN_POSTS = 100          
POSTS_TO_CHECK = 0      
WORKERS_PER_ACCOUNT = 1 

# --- CONFIGURACION DE ENFRIAMIENTO ---
COOLDOWN_MINUTES = 60  # Tiempo que descansa una cuenta si recibe advertencia

# --- RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
user_home = os.path.expanduser("~")
DESKTOP_DIR = os.path.join(user_home, "Desktop")

if not os.path.exists(DESKTOP_DIR):
    DESKTOP_DIR = SCRIPT_DIR

CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.txt')
HISTORY_FILE = os.path.join(SCRIPT_DIR, f'history_{TARGET_PROFILE}.txt')
CSV_FILENAME = os.path.join(DESKTOP_DIR, f'leads_big_accounts_{TARGET_PROFILE}_SEGUIDOS.csv')
SESSION_DIR = SCRIPT_DIR
PROXY_COUNTRIES = ['us']

# --- GLOBALES ---
STATS_LOCK = threading.Lock()
POOL_LOCK = threading.Lock() 
SESSION_OBJECTS = {} 
ACCOUNTS_POOL = [] # Lista simple de usuarios
COOLDOWN_DICT = {} # {usuario: timestamp_liberacion}
BANNED_ACCOUNTS = set()
VISITED_USERS = set() 
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

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                VISITED_USERS.add(line.strip())
        print(f"Historial cargado: {len(VISITED_USERS)} usuarios ya ignorados.")

def save_visit_async(username):
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
                        writer.writerow(["Usuario", "URL", "Seguidores", "Publicaciones", "Estado"])
                    
                    count = 0
                    while not WRITE_QUEUE.empty() and count < 50:
                        data = WRITE_QUEUE.get()
                        if data:
                            writer.writerow(data)
                            WRITE_QUEUE.task_done()
                            count += 1
                    f.flush()
                    os.fsync(f.fileno()) 
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
            sleep=False, 
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

# --- FUNCIONES DE GESTION DE CUENTAS (SMART POOL) ---

def freeze_account(username):
    """Pone la cuenta en el congelador temporalmente."""
    release_time = time.time() + (COOLDOWN_MINUTES * 60)
    with POOL_LOCK:
        COOLDOWN_DICT[username] = release_time
        print(f"\n[ENFRIAMIENTO] {username} pausada por {COOLDOWN_MINUTES} min (Error temp).")

def kill_account_permanent(username):
    """Elimina la cuenta definitivamente (Credenciales malas)."""
    with POOL_LOCK:
        if username in ACCOUNTS_POOL:
            ACCOUNTS_POOL.remove(username)
        if username in COOLDOWN_DICT:
            del COOLDOWN_DICT[username]
    if username in SESSION_OBJECTS:
        del SESSION_OBJECTS[username]
    print(f"\n[FATAL] Cuenta {username} eliminada permanentemente.")

def get_next_available_account():
    """Busca una cuenta viva que no esté en enfriamiento. Si todas descansan, duerme."""
    while True:
        with POOL_LOCK:
            # 1. Si no hay cuentas vivas en total, fin del juego.
            if not ACCOUNTS_POOL:
                return None
            
            # 2. Revisar si alguien salió del enfriamiento
            now = time.time()
            accounts_to_release = []
            for acc, release_ts in COOLDOWN_DICT.items():
                if now >= release_ts:
                    accounts_to_release.append(acc)
            
            for acc in accounts_to_release:
                del COOLDOWN_DICT[acc]
                print(f"[RECUPERADA] {acc} vuelve al trabajo.")

            # 3. Buscar candidatos disponibles
            candidates = [acc for acc in ACCOUNTS_POOL if acc not in COOLDOWN_DICT]

            if candidates:
                # Rotación simple (toma el primero y lo manda al final para Round Robin)
                chosen = candidates[0]
                ACCOUNTS_POOL.remove(chosen)
                ACCOUNTS_POOL.append(chosen)
                return chosen
            
            # 4. Si no hay candidatos, calcular tiempo de espera
            if COOLDOWN_DICT:
                next_release = min(COOLDOWN_DICT.values())
                sleep_seconds = next_release - now
                if sleep_seconds < 0: sleep_seconds = 1
            else:
                return None # Should not happen if pool not empty

        # Si llegamos aquí, es que hay cuentas pero todas duermen.
        print(f"[SISTEMA PAUSADO] Esperando {int(sleep_seconds)}s a que se recuperen cuentas...", end='\r')
        time.sleep(sleep_seconds + 1) # Dormir y reintentar loop

# ----------------------------------------------------

def worker_task(target_user, account_user):
    global PROCESSED_COUNT, SAVED_COUNT
    
    with POOL_LOCK:
        if account_user in COOLDOWN_DICT: return

    L = SESSION_OBJECTS.get(account_user)
    if not L: return

    try:
        # Pausa leve
        time.sleep(random.uniform(3.0, 6.0)) 

        profile = instaloader.Profile.from_username(L.context, target_user)
        
        # Filtros rápidos
        if profile.is_private: return

        # Si descartamos, usamos \r para que se sobrescriba (ahorra espacio visual)
        
        # --- NUEVA LÓGICA DE FILTRADO POR RANGO ---
        # Verificamos si NO está en el rango (Menor que Mínimo O Mayor que Máximo)
        if not (MIN_FOLLOWERS <= profile.followers <= MAX_FOLLOWERS):
            VISITED_USERS.add(target_user)
            save_visit_async(target_user)
            with STATS_LOCK:
                PROCESSED_COUNT += 1
                # Mensaje efímero (se borra con el siguiente)
                print(f"[{PROCESSED_COUNT}|{SAVED_COUNT}] {target_user:<15} | Followers: {profile.followers} | DESCARTADO", end='\r')
            return
        # --------------------------------------------

        if profile.mediacount < MIN_POSTS:
            VISITED_USERS.add(target_user)
            save_visit_async(target_user)
            with STATS_LOCK:
                PROCESSED_COUNT += 1
                # Mensaje efímero
                print(f"[{PROCESSED_COUNT}|{SAVED_COUNT}] {target_user:<15} | < Posts     | DESCARTADO", end='\r')
            return

        # --- SI LLEGA AQUI, ES UN LEAD ---
        
        VISITED_USERS.add(target_user)
        save_visit_async(target_user)

        url = f"https://instagram.com/{target_user}"
        WRITE_QUEUE.put([target_user, url, profile.followers, profile.mediacount, "CUMPLE REQ"])
        
        with STATS_LOCK: 
            SAVED_COUNT += 1
            PROCESSED_COUNT += 1
            # Mensaje FIJO (sin \r) para que quede registrado visualmente en la consola
            print(f"[{PROCESSED_COUNT}|{SAVED_COUNT}] {target_user:<15} | F:{profile.followers} P:{profile.mediacount} | >>> GUARDADO <<<")

    except Exception as e:
        err = str(e)
        # Ahora que sleep=False, los errores 429 caerán aquí inmediatamente
        if "401" in err or "429" in err or "wait" in err.lower() or "too many queries" in err.lower():
            freeze_account(account_user)
        elif "login" in err.lower() or "challenge" in err.lower():
            freeze_account(account_user)

def main():
    global ACCOUNTS_POOL
    load_history() 
    
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

    print(f"\n>>> INICIANDO SCRAPING DE SEGUIDOS CON SMART POOL <<<")
    print(f">>> Rango aceptado: {MIN_FOLLOWERS} a {MAX_FOLLOWERS} seguidores.")

    writer_thread = CSVWriterThread(CSV_FILENAME)
    writer_thread.start()

    try:
        # Bucle principal de Maestros
        while True:
            current_master = get_next_available_account()
            
            if not current_master:
                print("\n[FATAL] No quedan cuentas operativas.")
                break

            print(f"\n[MAESTRO ACTIVO]: {current_master}")

            try:
                L_master = SESSION_OBJECTS[current_master]
                target = instaloader.Profile.from_username(L_master.context, TARGET_PROFILE)
                
                print(f"Obteniendo lista de SEGUIDOS de {TARGET_PROFILE}...")
                followees_iter = target.get_followees()
                
                with ThreadPoolExecutor(max_workers=len(ACCOUNTS_POOL)) as executor:
                    for followee in followees_iter:
                        
                        # --- SELECCION DINAMICA DE WORKER ---
                        worker_acc = get_next_available_account()
                        
                        if not worker_acc:
                            print("[CRITICO] Pool vacío durante ejecución.")
                            break # Rompe loop de seguidores para intentar recuperar cuentas arriba

                        # --- RETOMAR ---
                        if followee.username in VISITED_USERS:
                            if len(VISITED_USERS) % 200 == 0:
                                print(f"[INFO] Saltando usuarios ya visitados...", end='\r')
                            continue
                        
                        executor.submit(worker_task, followee.username, worker_acc)
                        time.sleep(random.uniform(0.3, 0.8))
                
                print("\n--- LISTA DE SEGUIDOS COMPLETADA ---")
                break

            except KeyboardInterrupt:
                raise

            except Exception as e:
                err = str(e)
                print(f"\n[ERROR MAESTRO] {current_master}: {err}")
                
                if "429" in err or "401" in err or "wait" in err.lower():
                    freeze_account(current_master)
                else:
                    # Si es error grave desconocido, congelamos por seguridad
                    freeze_account(current_master)
                
                print(">>> Rotando maestro...\n")
                time.sleep(2)

    except KeyboardInterrupt:
        print("\nDeteniendo...")
    finally:
        writer_thread.stop()
        print(f"\nFinalizado. CSV en: {CSV_FILENAME}")
        print(f"Historial actualizado en: {HISTORY_FILE}")

if __name__ == "__main__":
    main()