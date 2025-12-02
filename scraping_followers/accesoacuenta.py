import instaloader
import os

# --- CONFIGURACIÓN ---
MY_USER = "fabiangoltra44"
# Copia el sessionid fresco desde el navegador (F12 > Application > Cookies)
SESSION_ID = "448472755%3Ab3qdFfVjsqLIIj%3A28%3AAYhX5o0h-gXx27YOeE8Hb4KFJc8veGSEcu3_WZf_KA" 
# User Agent genérico de Windows para evitar bloqueo por dispositivo desconocido
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Ruta al Escritorio
desktop = os.path.join(os.path.expanduser("~"), "Escritorio")
SESSION_FILE = os.path.join(desktop, f"{MY_USER}.session")
# ---------------------

def crear_sesion():
    print(f"Usuario: {MY_USER}")
    
    # Inicializar con User Agent
    L = instaloader.Instaloader(user_agent=USER_AGENT)
    
    # Inyectar cookie manualmente
    L.context._session.cookies.set("sessionid", SESSION_ID)
    L.context.username = MY_USER
    
    print("Verificando acceso...")

    try:
        # Intentar obtener datos propios para validar la cookie
        me = instaloader.Profile.from_username(L.context, MY_USER)
        print(f"Acceso correcto. ID: {me.userid}")
        
        # Guardar en Escritorio
        L.save_session_to_file(filename=SESSION_FILE)
        print(f"Sesion guardada en: {SESSION_FILE}")
        print("Ya puedes ejecutar el script principal.")

    except Exception as e:
        print("Fallo la verificacion.")
        print(f"Error: {e}")
        print("Revisa el sessionid.")

if __name__ == "__main__":
    crear_sesion()