import time
import os
import random
import shutil
import json
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- CONFIGURACIÓN ---
TARGET_PROFILE = "barackobama"  # Usuario al que robaremos los seguidores
MAX_AVATARS = 50                # Cantidad de fotos a descargar
HEADLESS_MODE = False           # False para ver el navegador (recomendado)

# CREDENCIALES PROXY
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_23e53168-zone-residential_proxy1-country-ar"
PROXY_PASS = "ei0g975bijby"

# --- RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(SCRIPT_DIR, 'all.txt')
AVATARES_DIR = os.path.join(SCRIPT_DIR, "AVATARES")

if not os.path.exists(AVATARES_DIR):
    os.makedirs(AVATARES_DIR)

# --- UTILIDADES ---

def create_proxy_auth_folder(host, port, user, password, session_id):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 3,
        "name": "Chrome Proxy Auth",
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
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    with open(os.path.join(folder_name, "manifest.json"), 'w') as f:
        f.write(manifest_json)
    with open(os.path.join(folder_name, "background.js"), 'w') as f:
        f.write(background_js)
    return folder_name

def load_accounts_from_txt():
    """Lee el archivo all.txt buscando el formato user:pass...:[json]"""
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"[ERROR] No existe {ACCOUNTS_FILE}")
        return []

    loaded_accounts = []
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or "[" not in line:
                    continue

                try:
                    idx = line.find("[")
                    cred_part = line[:idx]
                    json_part = line[idx:]

                    user = cred_part.split(':')[0]
                    cookies = json.loads(json_part)

                    session_id = next((c['value'] for c in cookies if c['name'] == 'sessionid'), None)

                    if session_id:
                        loaded_accounts.append({'user': user, 'sessionid': session_id})
                except:
                    pass
    except Exception as e:
        print(f"[ERROR LECTURA] {e}")

    print(f"[SISTEMA] Cuentas cargadas: {len(loaded_accounts)}")
    return loaded_accounts

def dismiss_popups(driver):
    buttons_text = ["Not Now", "Ahora no", "Cancel", "Cancelar"]
    for _ in range(2):
        for txt in buttons_text:
            try:
                xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                for btn in elements:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
            except:
                pass

def download_image(url, username):
    if not url:
        return False
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            file_path = os.path.join(AVATARES_DIR, f"{username}.jpg")
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return True
    except:
        pass
    return False

def extract_pfp_high_res(driver):
    """
    Intenta obtener la imagen HD haciendo clic en el header.
    Si falla, devuelve la normal.
    """
    try:
        wait = WebDriverWait(driver, 5)

        header_img = wait.until(EC.element_to_be_clickable((By.XPATH, "//header//img")))
        driver.execute_script("arguments[0].click();", header_img)

        high_res_xpath = "//div[@role='dialog']//img"
        wait.until(EC.presence_of_element_located((By.XPATH, high_res_xpath)))

        time.sleep(1.5)

        modal_imgs = driver.find_elements(By.XPATH, high_res_xpath)
        for img in modal_imgs:
            src = img.get_attribute("src")
            width = img.size.get('width', 0)
            if src and "http" in src and width > 150:
                return src

    except Exception:
        pass

    try:
        img = driver.find_element(By.XPATH, "//header//img")
        return img.get_attribute("src")
    except:
        return None

def open_following_list(driver):
    """
    Abre la lista de SEGUIDOS de forma robusta en IG.
    Evita el bug de mobile donde el click abre historias.
    """
    wait = WebDriverWait(driver, 12)

    # Anti-stories (opcional pero útil): desactiva clicks sobre el avatar si está superpuesto
    try:
        driver.execute_script("""
        let avatar = document.querySelector('header img');
        if (avatar) avatar.style.pointerEvents = 'none';
        """)
    except:
        pass

    dismiss_popups(driver)

    # Click robusto: por href real (NO posicional)
    following_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/following/')]"))
    )
    driver.execute_script("arguments[0].click();", following_btn)

    # Esperar modal
    wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
    time.sleep(2.5)

def run_scraper_session(account, current_count):
    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- [BOT: {account['user']}] -> Target: {TARGET_PROFILE} ---")

    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)

    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument("--disable-notifications")
    options.add_argument('--lang=en-US')
    if HEADLESS_MODE:
        options.add_argument('--headless=new')

    driver = None

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        driver.set_window_size(1280, 900)  # Tamaño móvil

        # Login con Cookie
        driver.get("https://www.instagram.com/404")
        time.sleep(2)
        driver.add_cookie({
            'name': 'sessionid',
            'value': account['sessionid'],
            'domain': '.instagram.com',
            'path': '/',
            'secure': True,
            'httpOnly': True
        })

        # Ir al perfil
        print(f"Navegando a {TARGET_PROFILE}...")
        driver.get(f"https://www.instagram.com/{TARGET_PROFILE}/")
        time.sleep(5)
        dismiss_popups(driver)

        # --- APERTURA DE LISTA "SEGUIDOS" (FIX REAL) ---
        try:
            print("Abriendo lista de SEGUIDOS (por /following/)...")
            open_following_list(driver)
            print("Lista abierta.")
        except Exception as e:
            print(f"[ERROR] No se pudo abrir la lista de seguidos (privado/bloqueo/layout): {e}")
            return "CONTINUE", current_count

        # --- BUCLE DE SCROLL Y EXTRACCIÓN ---
        try:
            dialog_box = driver.find_element(By.XPATH, "//div[@role='dialog']")
        except:
            print("No se encontró el diálogo de usuarios.")
            return "CONTINUE", current_count

        processed_users = set()
        consecutive_fails = 0

        while current_count < MAX_AVATARS:
            dismiss_popups(driver)

            try:
                links = dialog_box.find_elements(By.TAG_NAME, "a")
            except:
                break

            new_candidates = []
            last_element = None

            for link in links:
                try:
                    last_element = link
                    href = link.get_attribute('href')
                    if not href or 'instagram.com' not in href:
                        continue

                    clean_user = href.strip('/').split('/')[-1]

                    if clean_user in [TARGET_PROFILE, account['user'], 'explore', 'reels']:
                        continue

                    if clean_user not in processed_users:
                        new_candidates.append(clean_user)
                        processed_users.add(clean_user)
                except:
                    pass

            if not new_candidates:
                consecutive_fails += 1
                if consecutive_fails > 8:
                    print("Fin de la lista o bloqueo de scroll.")
                    break

                print("Haciendo Scroll...")
                if last_element:
                    driver.execute_script("arguments[0].scrollIntoView(true);", last_element)
                else:
                    try:
                        dialog_box.send_keys(Keys.END)
                    except:
                        pass

                time.sleep(3)
                continue

            consecutive_fails = 0
            main_window = driver.current_window_handle

            # --- PROCESAR CADA USUARIO EN PESTAÑA NUEVA ---
            for user in new_candidates:
                if current_count >= MAX_AVATARS:
                    break

                print(f"Extrayendo foto de: {user}...", end="")

                try:
                    driver.execute_script(f"window.open('https://www.instagram.com/{user}/', '_blank');")
                    WebDriverWait(driver, 8).until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])

                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "header")))

                    img_url = extract_pfp_high_res(driver)

                    driver.close()
                    driver.switch_to.window(main_window)

                    if img_url:
                        if download_image(img_url, user):
                            print(" [OK HD]")
                            current_count += 1
                        else:
                            print(" [ERR DESCARGA]")
                    else:
                        print(" [NO IMG]")

                    time.sleep(random.uniform(1.5, 3))

                except Exception as e:
                    err_type = type(e).__name__
                    cur_url = ""
                    title = ""
                    try:
                        cur_url = driver.current_url
                        title = driver.title
                    except:
                        pass

                    print(f" [SKIP {err_type}] url={cur_url} title={title} repr={repr(e)}")

                # Recuperar foco
                try:
                    while len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.close()
                    driver.switch_to.window(main_window)
                except:
                    break

            if last_element:
                driver.execute_script("arguments[0].scrollIntoView(true);", last_element)
            time.sleep(2)

    except Exception as e:
        print(f"Error crítico en sesión: {e}")
    finally:
        if driver:
            driver.quit()
        if os.path.exists(plugin_path):
            shutil.rmtree(plugin_path)

    return "DONE", current_count

def main():
    print("--- RECOLECTOR DE AVATARES HD (all.txt) ---")
    accounts = load_accounts_from_txt()
    if not accounts:
        return

    total_dl = 0
    acc_idx = 0

    while total_dl < MAX_AVATARS:
        if acc_idx >= len(accounts):
            print("Todas las cuentas utilizadas.")
            break

        acc = accounts[acc_idx]
        _, total_dl = run_scraper_session(acc, total_dl)
        acc_idx += 1

        if total_dl >= MAX_AVATARS:
            print(f"\n¡META COMPLETADA! {total_dl} fotos descargadas.")
            break

        time.sleep(5)

if __name__ == "__main__":
    main()
