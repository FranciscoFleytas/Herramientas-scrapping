import time
import os
import json
import random
import shutil
import requests
import datetime
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

# ==========================================
# 0. CONFIGURACION Y ENTORNO
# ==========================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '.env') 
if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), '.env')

load_dotenv(ENV_PATH)

# RUTAS
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

# CREDENCIALES
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

# PROXY
PROXY_ENABLED = os.getenv("BRIGHTDATA_PROXY_ENABLED", "0") == "1"
PROXY_HOST = os.getenv("BRIGHTDATA_PROXY_HOST")
PROXY_PORT = os.getenv("BRIGHTDATA_PROXY_PORT")
PROXY_USER = os.getenv("BRIGHTDATA_PROXY_USER")
PROXY_PASS = os.getenv("BRIGHTDATA_PROXY_PASSWORD")

# AI (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "gemini-3-flash-preview:latest")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

# CONFIGURACION BOT
ESTADO_TRIGGER = "Escribir" 
ESTADO_FINAL = "Contactado"
MODO_HEADLESS = False
USE_TELEGRAM = True  # Cambiar a True para usar Telegram para aprobación antes de enviar mensajes
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ==========================================
# 1. UTILIDADES
# ==========================================

def create_proxy_auth_folder(host, port, user, password):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 3,
        "name": "Chrome Proxy Auth V3",
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
        return {{ authCredentials: {{ username: "{user}", password: "{password}" }} }};
    }}
    chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
    """
    folder_name = os.path.join(SCRIPT_DIR, f'proxy_ext_{random.randint(1000,9999)}')
    if not os.path.exists(folder_name): os.makedirs(folder_name)
    with open(os.path.join(folder_name, "manifest.json"), 'w') as f: f.write(manifest_json)
    with open(os.path.join(folder_name, "background.js"), 'w') as f: f.write(background_js)
    return folder_name

def remove_non_bmp(text):
    return ''.join(c for c in text if c <= '\uFFFF')

def clean_handle_name(text):
    # Limpieza agresiva para sacar el nombre del usuario
    text = re.sub(r'\d+$', '', text)
    text = text.replace('.', ' ').replace('_', ' ')
    parts = text.split()
    if parts: return parts[0].capitalize()
    return text.capitalize()

def human_type(element, text):
    safe_text = remove_non_bmp(text)
    for char in safe_text:
        element.send_keys(char)
        time.sleep(random.uniform(0.01, 0.02))

def dismiss_popups(driver):
    textos = ["Ahora no", "Not Now", "Cancelar", "Cancel", "Activar"]
    for txt in textos:
        try:
            xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"   
            botones = driver.find_elements(By.XPATH, xpath)
            for btn in botones:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
        except: pass

def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

# ==========================================
# 2. INFRAESTRUCTURA
# ==========================================

def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument(f'--user-agent={DESKTOP_UA}')
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US") 
    plugin_path = None
    if PROXY_ENABLED and PROXY_HOST:
        print(f"[INFO] Proxy Activado: {PROXY_HOST}")
        plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS)
        options.add_argument(f'--load-extension={plugin_path}')
    if MODO_HEADLESS: options.add_argument('--headless=new')
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
    driver.set_window_size(1280, 850)
    driver.proxy_plugin_path = plugin_path
    return driver

def load_account():
    if not os.path.exists(CUENTAS_FILE): return None
    try:
        with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list): return data[0]
            return data
    except: return None

def login_with_cookie(driver, account):
    print(f"[LOGIN] {account['user']}...")
    driver.get("https://www.instagram.com/404")
    time.sleep(2)
    driver.add_cookie({'name': 'sessionid', 'value': account['sessionid'], 'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True})
    driver.get("https://www.instagram.com/")
    time.sleep(2)
    dismiss_popups(driver)
    if "login" in driver.current_url:
        print("[ERROR] Cookie invalida.")
        return False
    return True

# ==========================================
# TELEGRAM: APROBACION + EDITAR TEXTO (RAPIDO, MISMA LOGICA)
# ==========================================
TG_SESSION = requests.Session()
TG_SESSION.headers.update({"Connection": "keep-alive"})

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_APPROVAL_TIMEOUT = int(os.getenv("TELEGRAM_APPROVAL_TIMEOUT", "300"))

# Offset global: evita releer backlog en cada aprobación
TG_OFFSET = None

def tg_api(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"

def tg_init_offset() -> None:
    """Flush backlog 1 sola vez al inicio del script."""
    global TG_OFFSET
    if not TELEGRAM_BOT_TOKEN:
        TG_OFFSET = None
        return
    try:
        r = TG_SESSION.get(tg_api("getUpdates"), params={"timeout": 0}, timeout=15)
        r.raise_for_status()
        data = r.json().get("result", [])
        TG_OFFSET = (data[-1]["update_id"] + 1) if data else None
    except Exception:
        TG_OFFSET = None

def tg_send_message(chat_id: str, text: str, reply_markup: dict | None = None) -> None:
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        raise RuntimeError("Telegram no configurado: falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")

    payload = {"chat_id": chat_id, "text": text}  # sin parse_mode (evita 400 por Markdown)
    if reply_markup:
        payload["reply_markup"] = reply_markup

    r = TG_SESSION.post(tg_api("sendMessage"), json=payload, timeout=20)
    if r.status_code != 200:
        try:
            print("[TELEGRAM] sendMessage error:", r.status_code, r.text)
        except Exception:
            pass
        r.raise_for_status()

def tg_answer_callback(callback_query_id: str, text: str = "") -> None:
    payload = {"callback_query_id": callback_query_id, "text": text}
    # usar session + timeout corto (no frenar el bot por esto)
    try:
        TG_SESSION.post(tg_api("answerCallbackQuery"), json=payload, timeout=8)
    except Exception:
        pass

def tg_buttons_for(approval_id: str, mode: str = "default") -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Aprobar", "callback_data": f"approve:{approval_id}"},
                {"text": "❌ Rechazar", "callback_data": f"reject:{approval_id}"},
            ]
        ]
    }

def tg_send_approval(chat_id: str, approval_id: str, lead_url: str, real_name: str, bio_text: str, mensajes: list[str]) -> None:
    preview = "\n\n".join(mensajes)
    text = (
        f"✅ Aprobar DM antes de enviar\n"
        f"Prospecto: {real_name}\n"
        f"URL: {lead_url}\n\n"
        f"Bio: {bio_text[:400]}\n\n"
        f"Mensaje:\n{preview}"
    )
    tg_send_message(chat_id, text, reply_markup=tg_buttons_for(approval_id, "default"))

def tg_wait_decision(approval_id: str, timeout_s: int) -> bool:
    """
    Devuelve True si aprueban, False si rechazan o timeout.
    """
    global TG_OFFSET

    deadline = time.time() + timeout_s

    while time.time() < deadline:
        params = {
            "timeout": 50,
            "allowed_updates": ["callback_query"],
        }
        if TG_OFFSET is not None:
            params["offset"] = TG_OFFSET

        try:
            r = TG_SESSION.get(tg_api("getUpdates"), params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
        except Exception:
            time.sleep(0.2)
            continue

        updates = data.get("result", [])
        if not updates:
            continue

        for upd in updates:
            try:
                TG_OFFSET = upd["update_id"] + 1
            except Exception:
                pass

            cq = upd.get("callback_query")
            if cq:
                cb_data = cq.get("data", "")
                cq_id = cq.get("id")

                if cb_data == f"approve:{approval_id}":
                    tg_answer_callback(cq_id, "Aprobado ✅")
                    return True

                if cb_data == f"reject:{approval_id}":
                    tg_answer_callback(cq_id, "Rechazado ❌")
                    return False

    return False



# ==========================================
# 3. NOTION
# ==========================================

def get_leads_to_write():
    print(f"[NOTION] Consultando...")
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    payload = {"filter": {"property": "Estado", "status": {"equals": ESTADO_TRIGGER}}}
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        leads = []
        for res in data.get("results", []):
            try:
                props = res["properties"]
                name_notion = props["Cliente"]["title"][0]["text"]["content"] if props["Cliente"]["title"] else "Partner"
                raw_url = props["URL"]["url"]
                if not raw_url: continue
                leads.append({"id": res["id"], "name": name_notion, "url": raw_url})
            except: continue
        return leads
    except: return []

def update_lead_status(page_id, status=ESTADO_FINAL):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    payload = {"properties": {"Estado": {"status": {"name": status}}, "Ultimo Mensaje": {"date": {"start": datetime.datetime.now().isoformat()}}}}
    requests.patch(url, json=payload, headers=headers)
    print(f"[NOTION] Status actualizado a: {status}.")

# ==========================================
# 4. DATOS REALES (Fixed Logic)
# ==========================================

def get_handle_from_url(url):
    try:
        if "instagram.com" in url:
            parts = url.rstrip('/').split('/')
            return parts[-1]
    except: pass
    return "Partner"

def get_real_name_and_bio(driver, lead):
    url = lead['url']
    handle = get_handle_from_url(url)
    
    # 1. Prioridad: Meta Title
    real_name = ""
    try:
        meta_title = driver.find_element(By.XPATH, "//meta[@property='og:title']").get_attribute("content")
        if "(" in meta_title:
            extracted = meta_title.split('(')[0].strip()
            if extracted and "Instagram" not in extracted:
                real_name = extracted.split(' ')[0]
    except: pass

    # 2. Fallback: H1
    if not real_name:
        try:
            h1 = driver.find_element(By.TAG_NAME, "h1")
            if h1 and h1.text: real_name = h1.text.split(' ')[0]
        except: pass

    # 3. Fallback: Handle limpio (Nunca "There")
    if not real_name:
        real_name = clean_handle_name(handle)

    # Bio
    bio_text = "Content Creator"
    try:
        bio_element = driver.find_element(By.XPATH, "//meta[@property='og:description']")
        content = bio_element.get_attribute("content")
        if content: bio_text = content.split('followers')[0].replace('See Instagram photos', '').strip()
    except: pass

    real_name = remove_non_bmp(real_name).strip()
    return real_name.capitalize(), bio_text

# ==========================================
# 5. OLLAMA (Prompt Restaurado del Backup)
# ==========================================

def generate_ai_message(real_name, bio_text):
    # Prompt del Backup adaptado para Ollama (Inglés + Corto)
    prompt = f"""
    TASK: Send a friendly, curious DM.
        BIO CONTEXT: "{bio_text}"
        
        MANDATORY FORMAT: [Statement] \n\n [Question]?
        You MUST use \n\n for line breaks
        
        RULES:
        1. Tone: Casual, appreciative, direct. No marketing jargon.
        2. NO generic greetings ("Hello", "Hi"). Start with the statement.
        3. NO Emojis.
        
        EXAMPLES:
        - "Your content is super clean \n\n Do you have help with the edits?"
        - "Your vibe is super clean \n\n Is it just you managing this?"
        - "Love your style \n\n How do you come up with ideas?"
        - "Your feed is really cohesive \n\n Do you plan all posts in advance?"
    """
    
    api_url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    headers = { "Content-Type": "application/json" }
    if OLLAMA_API_KEY: headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    try:
        response = requests.post(api_url, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.5}}, headers=headers, timeout=OLLAMA_TIMEOUT)
        if response.status_code == 200:
            return response.json().get("response", "").strip().replace('"', '').replace('**', '')
        else:
            raise SystemExit(f"Ollama Error: {response.status_code}")
    except Exception as e:
        raise SystemExit(f"Ollama Connection Error: {e}")

def safe_generate_ai_message(real_name, bio_text):
    try:
        return generate_ai_message(real_name, bio_text)
    except Exception as e:
        print(f"[CRITICO] Error en generacion de mensaje AI: {e}")
        raise SystemExit("Script finalizado inmediatamente debido a fallo en AI.")

def clean_message_part(text):
    return remove_non_bmp(text).strip()

def send_dm(driver, lead):
    print(f"[Navegando] {lead['url']}")
    driver.get(lead['url'])
    time.sleep(random.uniform(2, 4))
    dismiss_popups(driver)
    
    real_name, bio_text = get_real_name_and_bio(driver, lead)
    print(f"   [Prospecto] {real_name}")

    full_msg = safe_generate_ai_message(real_name, bio_text)
    full_msg = full_msg.replace('<br><br>', '\n\n')  # Filtro para convertir <br><br> en saltos de línea
    mensajes = [clean_message_part(p) for p in full_msg.split('\n') if p.strip()]
    
    if len(mensajes) > 2: mensajes = mensajes[:2] # Hard limit 2
    
    print(f"   [Mensaje] {mensajes}")

    # ======= TELEGRAM APPROVAL GATE =======
    if USE_TELEGRAM:
        approval_id = f"{lead.get('id','noid')}:{int(time.time())}"
        try:
            tg_send_approval(
                chat_id=TELEGRAM_CHAT_ID,
                approval_id=approval_id,
                lead_url=lead["url"],
                real_name=real_name,
                bio_text=bio_text,
                mensajes=mensajes
            )
            ok = tg_wait_decision(approval_id, TELEGRAM_APPROVAL_TIMEOUT)
            if not ok:
                print("   [SKIP] Rechazado (o timeout) por Telegram.")
                update_lead_status(lead['id'], "NO CUMPLE REQ")
                return False
        except Exception as e:
            print(f"   [WARN] No se pudo pedir aprobacion por Telegram: {e}")
            # Si querés que SIN Telegram NO ENVÍE JAMÁS, cambiá esto a: return False
            return False
    # ======= FIN TELEGRAM APPROVAL GATE =======
    
    wait = WebDriverWait(driver, 8)
    entrado = False

    # Botones
    bots = ["//div[text()='Mensaje']", "//div[text()='Message']", "//div[@role='button'][contains(., 'Message')]"]
    for x in bots:
        try:
            el = driver.find_elements(By.XPATH, x)
            for e in el:
                if e.is_displayed():
                    e.click()
                    entrado = True
                    break
            if entrado: break
        except: pass
    
    if not entrado:
        try:
            js_click(driver, driver.find_element(By.XPATH, "//div[text()='Message']"))
            entrado = True
        except: pass

    if entrado:
        try:
            time.sleep(2)
            dismiss_popups(driver)
            box = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'] | //div[@role='textbox']")))
            box.click()
            time.sleep(1)
            
            for msg in mensajes:
                human_type(box, msg)
                time.sleep(0.02)
                box.send_keys(Keys.ENTER)
                time.sleep(random.uniform(2, 4))
            
            print("   [OK] Enviado.")
            return True
        except Exception as e:
            print(f"   [ERROR] Chat: {e}")
            return False
    return False

# ==========================================
# 6. MAIN
# ==========================================

def main():
    print(f"[INICIO] Bot V35 (Audit Fix)...")
    account = load_account()
    if not account: return
    leads = get_leads_to_write()
    print(f"[INFO] Leads: {len(leads)}")
    if not leads: return

    driver = setup_driver()
    try:
        if login_with_cookie(driver, account):
            for lead in leads:
                print(f"\n--- {lead['name']} ---")
                if send_dm(driver, lead):
                    update_lead_status(lead['id'])
                    wait = random.uniform(5, 10)
                    print(f"[ESPERA] {int(wait)}s...")
                    time.sleep(wait)
    except SystemExit as e:
        print(f"\n[STOP] {e}")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        if driver:
            try: shutil.rmtree(getattr(driver, 'proxy_plugin_path', ''))
            except: pass
            driver.quit()

if __name__ == "__main__":
    main()