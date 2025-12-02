import instaloader
import os
import time
import requests

# --- CONFIGURACION BRIGHT DATA ---
# Es vital crear la sesion con el MISMO proxy que usaras para scrapear
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# Construccion del Proxy
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

# --- RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.txt')

# User Agent de Windows para el Login
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def check_proxy():
    """Verifica que el proxy tenga salida antes de intentar login."""
    try:
        print("Verificando Proxy...", end=" ")
        res = requests.get("http://lumtest.com/myip.json", proxies={'http': PROXY_URL, 'https': PROXY_URL}, timeout=10, verify=False)
        if res.status_code == 200:
            print("OK.")
            return True
    except Exception as e:
        print(f"FALLO: {e}")
    return False

def generar_sesiones():
    if not os.path.exists(CUENTAS_FILE):
        print(f"ERROR: No existe {CUENTAS_FILE}")
        return

    # Verificar proxy primero
    if not check_proxy():
        print("ERROR CRITICO: El proxy no funciona. No se pueden generar sesiones.")
        return

    print(f"--- LEYENDO CUENTAS ---")
    
    with open(CUENTAS_FILE, 'r') as f:
        lines = f.readlines()

    for line in lines:
        if ':' not in line: continue
        
        parts = line.strip().split(':')
        username = parts[0].strip()
        password = parts[1].strip()
        
        print(f"\nProcesando: {username}...")
        
        # Instaloader con Proxy configurado
        L = instaloader.Instaloader(user_agent=USER_AGENT)
        L.context._session.proxies = {'http': PROXY_URL, 'https': PROXY_URL}
        L.context._session.verify = False # Ignorar SSL del proxy para evitar errores
        
        session_file = os.path.join(SCRIPT_DIR, f"{username}.session")

        try:
            # Intentar Login
            L.login(username, password)
            print(f"   [OK] Login exitoso.")
            L.save_session_to_file(filename=session_file)
            print(f"   [GUARDADO] {username}.session")

        except instaloader.TwoFactorAuthRequiredException:
            print(f"   [2FA] Se requiere verificacion.")
            
            # Si hay codigo en el TXT (3er parametro), usarlo. Si no, pedir manual.
            backup_code = parts[2].strip() if len(parts) > 2 else None
            
            if backup_code:
                print(f"   Usando codigo del TXT: {backup_code}")
                code = backup_code
            else:
                code = input("   >> Ingresa codigo SMS/App: ").strip()

            try:
                L.context.two_factor_login(code)
                L.save_session_to_file(filename=session_file)
                print(f"   [OK] 2FA verificado y sesion guardada.")
            except Exception as e:
                print(f"   [ERROR 2FA] {e}")

        except instaloader.BadCredentialsException:
            print(f"   [ERROR] Contraseña incorrecta.")
        
        except instaloader.ConnectionException as e:
            print(f"   [ERROR] Conexion/Proxy: {e}")
            
        except Exception as e:
            print(f"   [ERROR] {e}")

        time.sleep(2)

    print("\n--- FINALIZADO ---")

if __name__ == "__main__":
    generar_sesiones()