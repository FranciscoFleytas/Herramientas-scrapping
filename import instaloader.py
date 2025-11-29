import instaloader
import os
import urllib3

# Desactivar advertencias SSL del proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CREDENCIALES ---
ACCOUNTS = {
    "franciflee": "Va951753456!",      
    "fabiangoltra44": "Colon2501$"   
}

# --- DATOS DEL PROXY ---
PROXY_USER = "brd-customer-hl_23e53168-zone-scrapping_usser"
PROXY_PASS = "6p7y5qv5mz4q"
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"

def login_with_backup_code(username, password):
    print(f"\n--- Iniciando sesión para: {username} ---")
    
    L = instaloader.Instaloader()
    
    # 1. CONFIGURAR PROXY
    proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    L.context._session.proxies = {'http': proxy_url, 'https': proxy_url}
    L.context._session.verify = False 

    # 2. INTENTO DE LOGIN
    try:
        L.login(username, password)
        print(">> Login directo exitoso (Sin 2FA).")
    except instaloader.TwoFactorAuthRequiredException:
        print("\n[!] 2FA REQUERIDO")
        print("Ve a Configuración -> Seguridad -> Métodos Adicionales -> Códigos de respaldo.")
        
        # Limpieza de entrada para aceptar "1234 5678" o "12345678"
        code = input(">> Ingresa un CÓDIGO DE RECUPERACIÓN (8 dígitos): ").strip().replace(" ", "")
        
        try:
            L.two_factor_login(code)
            print(">> Código aceptado.")
        except instaloader.BadCredentialsException as e:
            print(f"xx Error: El código fue rechazado. Intenta con otro de la lista. Detalle: {e}")
            return
        except Exception as e:
            print(f"xx Error desconocido en 2FA: {e}")
            return

    except instaloader.ConnectionException as e:
        print(f"xx Error de conexión (Posible fallo de Proxy): {e}")
        return
    except instaloader.BadCredentialsException:
        print("xx Contraseña incorrecta.")
        return

    # 3. GUARDAR SESIÓN
    try:
        filename = f"{username}.session"
        L.save_session_to_file(filename=filename)
        print(f"vv Sesión guardada correctamente: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"xx No se pudo guardar el archivo de sesión: {e}")

if __name__ == "__main__":
    for user, pwd in ACCOUNTS.items():
        login_with_backup_code(user, pwd)
    
    print("\nPROCESO TERMINADO.")