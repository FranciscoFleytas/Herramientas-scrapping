import time
import os
import random
import shutil
import json
import re
import requests
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException


# ---------------- CONFIG ----------------
TARGET_PROFILE = "emilieculshaw"
MAX_AVATARS = 120
HEADLESS_MODE = True

# "followers" (seguidores) o "following" (seguidos)
LIST_TO_SCRAPE = "followers"

# Proxy
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER = "brd-customer-hl_fe5a76d4-zone-isp_proxy1"
PROXY_PASS = "ir29ecqpebov"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(SCRIPT_DIR, "all.txt")
AVATARES_DIR = os.path.join(SCRIPT_DIR, "AVATARES")
os.makedirs(AVATARES_DIR, exist_ok=True)


# ---------------- UTILIDADES ----------------

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
    folder_name = os.path.join(SCRIPT_DIR, f"proxy_auth_{session_id}")
    os.makedirs(folder_name, exist_ok=True)
    with open(os.path.join(folder_name, "manifest.json"), "w", encoding="utf-8") as f:
        f.write(manifest_json)
    with open(os.path.join(folder_name, "background.js"), "w", encoding="utf-8") as f:
        f.write(background_js)
    return folder_name


def load_accounts_from_txt():
    """Lee all.txt buscando formato ...:[json cookies] y extrae sessionid."""
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"[ERROR] No existe {ACCOUNTS_FILE}")
        return []

    loaded = []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "[" not in line:
                continue
            try:
                idx = line.find("[")
                cred_part = line[:idx]
                json_part = line[idx:]
                user = cred_part.split(":")[0].strip()
                cookies = json.loads(json_part)
                session_id = next((c.get("value") for c in cookies if c.get("name") == "sessionid"), None)
                if session_id:
                    loaded.append({"user": user, "sessionid": session_id})
            except:
                pass

    print(f"[SISTEMA] Cuentas cargadas: {len(loaded)}")
    return loaded


def dismiss_popups(driver):
    # Instagram cambia labels seguido, esto es “lo suficiente” para la mayoría.
    candidates = ["Not Now", "Ahora no", "Cancel", "Cancelar", "OK", "Aceptar", "Allow", "Permitir"]
    for _ in range(2):
        for txt in candidates:
            try:
                xpath = f"//button[contains(., '{txt}')] | //div[@role='button'][contains(., '{txt}')]"
                for el in driver.find_elements(By.XPATH, xpath):
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.4)
            except:
                pass


def clean_username_from_href(href: str):
    if not href:
        return None
    href = href.split("?")[0].rstrip("/")
    parts = href.split("/")
    if not parts:
        return None
    user = parts[-1].strip()
    return user or None


FORBIDDEN_URL_PARTS = ["/p/", "/explore/", "/direct/", "/stories/", "/reels/", "/tv/", "/accounts/"]


def is_profile_href_ok(href: str):
    if not href or "instagram.com" not in href:
        return False
    clean = href.split("?")[0]
    if any(x in clean for x in FORBIDDEN_URL_PARTS):
        return False
    return True


def improve_ig_image_url(url: str):
    """
    Muchas URLs de IG incluyen tamaños tipo s150x150, s320x320, etc.
    Intentamos subir a s1080x1080 cuando exista ese patrón.
    """
    if not url:
        return url

    # Reemplaza s###x### por s1080x1080
    url2 = re.sub(r"/s\d+x\d+/", "/s1080x1080/", url)

    # Algunos vienen como ...=s150x150&...
    url2 = re.sub(r"=s\d+x\d+(&|$)", r"=s1080x1080\1", url2)

    return url2


def download_image(url, username):
    if not url:
        return False
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200 and resp.content:
            path = os.path.join(AVATARES_DIR, f"{username}.jpg")
            with open(path, "wb") as f:
                f.write(resp.content)
            return True
    except:
        pass
    return False


def extract_hd_avatar_from_profile(driver):
    """
    Estrategia como tu script que sí funciona:
    1) meta og:image
    2) buscar img por alt
    """
    # 1) og:image suele ser lo más estable
    try:
        meta = driver.find_element(By.XPATH, "//meta[@property='og:image']")
        img_url = meta.get_attribute("content")
        if img_url:
            return improve_ig_image_url(img_url)
    except:
        pass

    # 2) Fallback por alt
    try:
        imgs = driver.find_elements(By.TAG_NAME, "img")
        for img in imgs:
            alt = (img.get_attribute("alt") or "").lower()
            if "profile picture" in alt or "foto del perfil" in alt:
                src = img.get_attribute("src")
                if src:
                    return improve_ig_image_url(src)
    except:
        pass

    # 3) Último fallback: header img
    try:
        header_imgs = driver.find_elements(By.XPATH, "//header//img")
        for img in header_imgs:
            src = img.get_attribute("src")
            if src and src.startswith("http"):
                return improve_ig_image_url(src)
    except:
        pass

    return None


def open_list_modal(driver, which):
    if which not in ("followers", "following"):
        raise ValueError("LIST_TO_SCRAPE debe ser 'followers' o 'following'")

    dismiss_popups(driver)

    href_part = f"/{which}/"
    print(f"Buscando botón por href '{href_part}'...")
    btn = WebDriverWait(driver, 12).until(
        EC.element_to_be_clickable((By.XPATH, f"//a[contains(@href, '{href_part}')]"))
    )
    driver.execute_script("arguments[0].click();", btn)
    print("Lista abierta.")
    time.sleep(3)


def get_dialog_and_scrollable(driver):
    dialog = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
    )
    # busca contenedor scrolleable típico del modal
    try:
        scrollable = dialog.find_element(
            By.XPATH,
            ".//div[contains(@style, 'overflow: hidden auto') or contains(@style, 'overflow-y: auto')]"
        )
        return dialog, scrollable
    except:
        return dialog, dialog


# ---------------- SCRAPER PRINCIPAL ----------------

def run_scraper_session(account, current_count):
    session_id_rand = str(random.randint(100000, 999999))
    print(f"\n--- [BOT: {account['user']}] -> Target: {TARGET_PROFILE} ({LIST_TO_SCRAPE}) ---")

    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, session_id_rand)

    options = uc.ChromeOptions()
    options.add_argument(f"--load-extension={os.path.abspath(plugin_path)}")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--password-store=basic")
    options.add_argument("--lang=en-US")

    if HEADLESS_MODE:
        options.add_argument("--headless=new")

    driver = None

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)

        # IMPORTANTE: Desktop viewport (tu script que funciona usa desktop, es más estable)
        driver.set_window_size(1280, 900)

        # login cookie
        driver.get("https://www.instagram.com/404")
        time.sleep(2)

        driver.add_cookie({
            "name": "sessionid",
            "value": account["sessionid"],
            "domain": ".instagram.com",
            "path": "/",
            "secure": True,
            "httpOnly": True
        })

        print(f"Navegando a {TARGET_PROFILE}...")
        driver.get(f"https://www.instagram.com/{TARGET_PROFILE}/")
        time.sleep(5)
        dismiss_popups(driver)

        # abrir modal followers/following
        try:
            open_list_modal(driver, LIST_TO_SCRAPE)
        except Exception as e:
            print(f"[ERROR] No se pudo abrir la lista: {repr(e)}")
            return "CONTINUE", current_count

        try:
            dialog, scrollable = get_dialog_and_scrollable(driver)
        except Exception as e:
            print(f"[ERROR] No se encontró el diálogo/modal: {repr(e)}")
            return "CONTINUE", current_count

        processed_users = set()
        consecutive_fails = 0
        MAX_CONSEC_FAILS = 15
        main_window = driver.current_window_handle

        # Espera inicial para que pinte items
        time.sleep(3)

        while current_count < MAX_AVATARS:
            dismiss_popups(driver)

            # agarrar links del dialog
            try:
                links = dialog.find_elements(By.TAG_NAME, "a")
            except Exception as e:
                print(f"[ERROR] No pude leer links del modal: {repr(e)}")
                break

            new_candidates = []
            last_elem = None

            for a in links:
                try:
                    href = a.get_attribute("href")
                    if not is_profile_href_ok(href):
                        continue

                    user = clean_username_from_href(href)
                    if not user:
                        continue

                    if user in (TARGET_PROFILE, account["user"]):
                        continue

                    if user not in processed_users:
                        processed_users.add(user)
                        new_candidates.append(user)

                    last_elem = a
                except:
                    pass

            if not new_candidates:
                consecutive_fails += 1
                if consecutive_fails >= MAX_CONSEC_FAILS:
                    print("Fin de la lista o no cargan más usuarios (timeout de scroll).")
                    break

                # scroll
                try:
                    if last_elem:
                        driver.execute_script("arguments[0].scrollIntoView(true);", last_elem)
                    else:
                        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable)
                except:
                    try:
                        scrollable.send_keys(Keys.END)
                    except:
                        pass

                time.sleep(2.5)
                continue

            consecutive_fails = 0

            for user in new_candidates:
                if current_count >= MAX_AVATARS:
                    break

                print(f"Extrayendo foto de: {user}...", end="")

                try:
                    # pestaña nueva como tu script funcional: about:blank y luego navegar
                    driver.execute_script("window.open('about:blank', '_blank');")
                    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)

                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(f"https://www.instagram.com/{user}/")

                    # Espera mínima a algo del DOM
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "img")))

                    img_url = extract_hd_avatar_from_profile(driver)

                    driver.close()
                    driver.switch_to.window(main_window)

                    if img_url and download_image(img_url, user):
                        current_count += 1
                        print(" [OK]")
                    else:
                        print(" [NO IMG/DL]")

                    time.sleep(random.uniform(1.8, 3.2))

                except TimeoutException as e:
                    # Esto era tu [SKIP] Message: vacío; ahora queda claro
                    print(f" [SKIP TIMEOUT] {repr(e)}")
                    try:
                        # cerrar pestaña extra si quedó abierta
                        if len(driver.window_handles) > 1:
                            driver.close()
                        driver.switch_to.window(main_window)
                    except:
                        pass

                except Exception as e:
                    print(f" [SKIP] {repr(e)}")
                    try:
                        while len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.close()
                        driver.switch_to.window(main_window)
                    except:
                        pass

            # scroll “natural” al final del lote
            try:
                if last_elem:
                    driver.execute_script("arguments[0].scrollIntoView(true);", last_elem)
            except:
                pass

            time.sleep(2)

    except Exception as e:
        print(f"Error crítico en sesión: {repr(e)}")

    finally:
        try:
            if driver:
                driver.quit()
        except:
            pass
        try:
            if os.path.exists(plugin_path):
                shutil.rmtree(plugin_path)
        except:
            pass

    return "DONE", current_count


def main():
    print("--- RECOLECTOR DE AVATARES (all.txt) ---")
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
