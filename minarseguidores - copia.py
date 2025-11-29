import instaloader
import time
import csv
import random
import os
from itertools import islice

# --- CONFIGURACIÓN ---
TARGET_PROFILE = "rkcoaching__"   # Perfil a analizar
MIN_FOLLOWERS = 5000         # Mínimo de seguidores
MY_USER = "fabiangoltra44"         # Tu usuario (debe coincidir con el archivo de sesión)

# Criterios de Engagement
POSTS_TO_CHECK = 10          # Cuantos posts revisar por persona
ENGAGEMENT_THRESHOLD = 0.03  # 3% (Si tiene menos de esto, es "low like")
BAD_POSTS_PERCENTAGE = 0.7   # 70% (Si el 70% son malos, se guarda)

# Rutas al Escritorio (para encontrar fácil los archivos)
desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
CSV_FILENAME = os.path.join(desktop, f'leads_{TARGET_PROFILE}.csv')
SESSION_FILE = os.path.join(desktop, f"{MY_USER}.session")
# ---------------------

def check_engagement(profile):
    """
    Retorna True si el usuario tiene engagement bajo en la mayoria de sus posts.
    """
    if profile.is_private:
        return False # No podemos ver likes de privados

    try:
        posts = profile.get_posts()
        # Tomamos solo los ultimos X posts (usando islice para no cargar todos)
        recent_posts = list(islice(posts, POSTS_TO_CHECK))
        
        if not recent_posts:
            return False

        low_like_posts = 0
        # Definimos el numero maximo de likes para considerar el post "malo"
        like_limit = profile.followers * ENGAGEMENT_THRESHOLD

        for post in recent_posts:
            if post.likes < like_limit:
                low_like_posts += 1

        # Calculamos ratio
        ratio = low_like_posts / len(recent_posts)
        
        # Si cumple el porcentaje de "malos posts" (ej. > 0.7)
        return ratio >= BAD_POSTS_PERCENTAGE

    except Exception as e:
        print(f"Error analizando posts: {e}")
        return False

def minar_seguidores():
    # Inicializar sin user agent específico, usará el de la sesión guardada
    L = instaloader.Instaloader()

    # Cargar Sesión
    # Busca el archivo .session explícitamente en el Escritorio o en la carpeta actual
    if os.path.exists(SESSION_FILE):
        try:
            print(f"Cargando sesion desde: {SESSION_FILE}")
            L.load_session_from_file(MY_USER, filename=SESSION_FILE)
        except Exception as e:
            print(f"Error cargando sesion: {e}")
            return
    elif os.path.exists(f"{MY_USER}.session"): # Intento secundario en carpeta local
        print(f"Cargando sesion local: {MY_USER}.session")
        L.load_session_from_file(MY_USER)
    else:
        print(f"No se encontro archivo de sesion para {MY_USER}")
        print("Ejecuta primero el script de creacion de sesion.")
        return

    print(f"Analizando perfil: {TARGET_PROFILE}")
    
    try:
        profile = instaloader.Profile.from_username(L.context, TARGET_PROFILE)
    except Exception as e:
        print(f"Error de acceso al perfil: {e}")
        return

    print(f"Total seguidores: {profile.followers}")
    print("Iniciando extraccion...")

    # Abrir CSV en el Escritorio
    with open(CSV_FILENAME, 'a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file, delimiter=';')
        
        # Escribir cabecera solo si el archivo está vacío
        if os.stat(CSV_FILENAME).st_size == 0:
             writer.writerow(["Cliente", "URL", "Estado", "Seguidores"])

        count = 0
        matches = 0
        
        try:
            for follower in profile.get_followers():
                try:
                    # 1. Filtro Rapido: Seguidores
                    if follower.followers >= MIN_FOLLOWERS:
                        
                        print(f"Analizando engagement de: {follower.username}...")
                        
                        # 2. Filtro Lento: Engagement (Entra a ver posts)
                        # Nota: Esto consume muchas peticiones
                        time.sleep(random.uniform(2, 4)) # Pausa antes de cargar posts
                        
                        if check_engagement(follower):
                            url = f"https://www.instagram.com/{follower.username}/"
                            print(f"MATCH PERFECTO: {follower.username}")
                            
                            # Opcional: Calcular promedio real para el CSV
                            writer.writerow([follower.username, url, "Por contactar", follower.followers, "Bajo"])
                            matches += 1
                        else:
                            print(f"Descartado (Engagement alto/normal): {follower.username}")

                except Exception as e:
                    print(f"Error leyendo perfil: {e}")

                count += 1

                # Pausas mas largas requeridas al cargar posts
                time.sleep(random.uniform(5, 10)) 

                if count % 10 == 0: # Reducido a cada 10 por la carga pesada
                    print(f"Procesados: {count} | Guardados: {matches}")
                    print("Pausa de seguridad (30s)...")
                    time.sleep(30)

        except KeyboardInterrupt:
            print("Detenido por usuario.")
        except Exception as e:
            print(f"Error de conexion: {e}")

    print(f"Finalizado. Resultados en: {CSV_FILENAME}")

if __name__ == "__main__":
    minar_seguidores()