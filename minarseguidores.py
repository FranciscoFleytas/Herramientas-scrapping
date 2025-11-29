import instaloader
import time
import csv
import random
import os
from itertools import islice

# --- CONFIGURACIÓN ---
TARGET_PROFILE = "mirin.max"   # Perfil a analizar
MIN_FOLLOWERS = 15000              # Mínimo de seguidores
MIN_POSTS = 100                   # Mínimo de publicaciones
MY_USER = "franciflee"        # Tu usuario

# Criterios de Engagement
POSTS_TO_CHECK = 10               # Cuantos posts revisar por persona
ENGAGEMENT_THRESHOLD = 0.03       # 3% (Si tiene menos de esto, es "low like")
BAD_POSTS_PERCENTAGE = 0.7        # 70% (Si el 70% son malos, se guarda)

# Rutas al Escritorio
desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
CSV_FILENAME = os.path.join(desktop, f'leads_{TARGET_PROFILE}.csv')
SESSION_FILE = os.path.join(desktop, f"{MY_USER}.session")
# ---------------------

def format_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def check_engagement(profile):
    """
    Retorna True si el usuario tiene engagement bajo en la mayoria de sus posts.
    """
    if profile.is_private:
        return False 

    try:
        # Pausa de seguridad antes de pedir posts (Evita 403/429)
        time.sleep(random.uniform(3, 5))
        
        posts = profile.get_posts()
        recent_posts = list(islice(posts, POSTS_TO_CHECK))
        
        if not recent_posts:
            return False

        low_like_posts = 0
        like_limit = profile.followers * ENGAGEMENT_THRESHOLD

        for post in recent_posts:
            if post.likes < like_limit:
                low_like_posts += 1
            # Breve pausa entre lectura de posts internos
            time.sleep(0.5)

        ratio = low_like_posts / len(recent_posts)
        return ratio >= BAD_POSTS_PERCENTAGE

    except Exception as e:
        print(f"Error analizando posts: {e}")
        return False

def minar_seguidores():
    L = instaloader.Instaloader()

    # Cargar Sesión
    if os.path.exists(SESSION_FILE):
        try:
            print(f"Cargando sesion desde: {SESSION_FILE}")
            L.load_session_from_file(MY_USER, filename=SESSION_FILE)
        except Exception as e:
            print(f"Error cargando sesion: {e}")
            return
    elif os.path.exists(f"{MY_USER}.session"):
        print(f"Cargando sesion local: {MY_USER}.session")
        L.load_session_from_file(MY_USER)
    else:
        print(f"No se encontro archivo de sesion para {MY_USER}")
        return

    print(f"Analizando perfil: {TARGET_PROFILE}")
    print(f"Filtros: >{MIN_FOLLOWERS} seguidores | >{MIN_POSTS} posts | Engagement < {ENGAGEMENT_THRESHOLD*100}%")
    
    try:
        profile = instaloader.Profile.from_username(L.context, TARGET_PROFILE)
        total_followers = profile.followers
    except Exception as e:
        print(f"Error acceso perfil: {e}")
        return
    
    global_start_time = time.time()

    print(f"Total seguidores: {total_followers}")
    print("Iniciando extraccion...")

    # Abrir CSV
    with open(CSV_FILENAME, 'a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file, delimiter=';')
        
        if os.stat(CSV_FILENAME).st_size == 0:
             # Se agrega columna Engagement para mantener coherencia
             writer.writerow(["Cliente", "URL", "Estado", "Seguidores", "Engagement"])

        count = 0
        matches = 0
        
        try:
            for follower in profile.get_followers():
                # Calculo ETR
                elapsed_total = time.time() - global_start_time
                if count > 0:
                    avg_time = elapsed_total / count
                    etr = format_time(avg_time * (total_followers - count))
                else:
                    etr = "..."

                try:
                    print(f"[{count}] ETR: {etr} | Analizando: {follower.username}...", end="\r")

                    seguidores = follower.followers
                    publicaciones = follower.mediacount

                    # 1. Filtro Rapido: Seguidores y Publicaciones
                    if seguidores >= MIN_FOLLOWERS and publicaciones >= MIN_POSTS:
                        
                        print(f"\nVerificando engagement: {follower.username} ({seguidores} segs)...")
                        
                        # 2. Filtro Lento: Engagement
                        if check_engagement(follower):
                            url = f"https://www.instagram.com/{follower.username}/"
                            print(f"MATCH: {follower.username} (Engagement Bajo detectado)")
                            
                            writer.writerow([follower.username, url, "Por contactar", seguidores, "Bajo"])
                            matches += 1
                        else:
                            # AQUI SE MENCIONA SI EL ENGAGEMENT ES ALTO
                            print(f"DESCARTADO: {follower.username} (Engagement Alto/Normal)")

                        # Pausa larga despues de analisis profundo
                        time.sleep(random.uniform(10, 15))

                except Exception as e:
                    print(f"\nError leyendo perfil: {e}")

                count += 1
                
                # Pausa estandar
                time.sleep(random.uniform(2, 4)) 

                if count % 10 == 0:
                    print(f"\nProcesados: {count} | Guardados: {matches}")
                    print("Pausa de seguridad (45s)...")
                    time.sleep(45)

        except KeyboardInterrupt:
            print("\nDetenido por usuario.")
        except Exception as e:
            print(f"\nError critico: {e}")

    print(f"Finalizado. Resultados en: {CSV_FILENAME}")

if __name__ == "__main__":
    minar_seguidores()