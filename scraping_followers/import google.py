import time
import os
import json
import random
import requests
import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import google.generativeai as genai

# --- GESTION DE RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

# --- TUS CREDENCIALES ---
NOTION_TOKEN = "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"
NOTION_DB_ID = "2b8f279cffec808ba6b3e43c7d449531"
GEMINI_API_KEY = "AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g"

# --- CONFIGURACION ---
ESTADO_TRIGGER = "Escribir" 
ESTADO_FINAL = "Contactado"
MODO_HEADLESS = False

# UA de Escritorio (Windows 10)
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash') 

# ==========================================
# 1. UTILIDADES ANTI-BOT
# ==========================================

def human_type(element, text):
    """Escribe letra por letra"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.04, 0.12))

def dismiss_popups(driver):
    """Cierra modales molestos"""
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
    """Click forzado por Javascript"""
    driver.execute_script("arguments[0].click();", element)

# ==========================================
# 2. INFRAESTRUCTURA
# ==========================================

def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument(f'--user-agent={DESKTOP_UA}')
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=es-AR") 
    
    if MODO_HEADLESS:
        options.add_argument('--headless=new')

    driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
    driver.set_window_size(1280, 850)
    return driver

def load_account():
    if not os.path.exists(CUENTAS_FILE):
        print("[ERROR] No existe cuentas.json")
        return None
    try:
        with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data[0] if isinstance(data, list) and len(data) > 0 else None
    except: return None

def login_with_cookie(driver, account):
    print(f"--- Logueando como {account['user']} ---")
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
    driver.get("https://www.instagram.com/")
    time.sleep(5)
    dismiss_popups(driver)

# ==========================================
# 3. CONEXION CON NOTION
# ==========================================

def get_leads_to_write():
    print(f"Consultando Notion...")
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
                name = props["Cliente"]["title"][0]["text"]["content"] if props["Cliente"]["title"] else "Friend"
                raw_url = props["URL"]["url"]
                if not raw_url: continue
                leads.append({"id": res["id"], "name": name, "url": raw_url if raw_url.startswith("http") else "https://" + raw_url})
            except: continue
        return leads
    except Exception as e:
        print(f"[ERROR NOTION] {e}")
        return []

def update_lead_status(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    now_iso = datetime.datetime.now().isoformat()
    
    payload_status = {
        "properties": {
            "Estado": { "status": { "name": ESTADO_FINAL } },
            "Ultimo Mensaje": { "date": { "start": now_iso } }
        }
    }
    payload_select = {
        "properties": {
            "Estado": { "select": { "name": ESTADO_FINAL } },
            "Ultimo Mensaje": { "date": { "start": now_iso } }
        }
    }
    
    print(f"   Actualizando Notion (ID: {page_id})...")
    response = requests.patch(url, json=payload_status, headers=headers)
    
    if response.status_code == 200:
        print(f"   [OK] Notion actualizado (Status): {ESTADO_FINAL}")
    else:
        if "validation_error" in response.text:
            print("   [INFO] Reintentando como tipo Select...")
            response_retry = requests.patch(url, json=payload_select, headers=headers)
            if response_retry.status_code == 200:
                print(f"   [OK] Notion actualizado (Select): {ESTADO_FINAL}")
            else:
                print(f"   [ERROR] Fallo actualizacion Notion: {response_retry.text}")
        else:
            print(f"   [ERROR] Notion: {response.text}")

# ==========================================
# 4. EXTRACCIÓN Y GEMINI (MEJORADO)
# ==========================================

def get_profile_data(driver):
    """Lee todo el texto visible del header del perfil"""
    try:
        # Esperamos a que cargue el encabezado del perfil
        header = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "header")))
        
        # Obtenemos todo el texto (Nombre, Bio, Seguidores, Links)
        raw_text = header.text.replace("\n", " | ")
        
        # Limpieza básica
        if len(raw_text) > 10:
            return raw_text
        return "Bio not found"
    except:
        return "Bio not found"

def generate_ai_message(name, raw_profile_data):
    # Prompt mejorado que recibe DATOS CRUDOS y los filtra
    prompt = f"""
   Role: Cold Outreach Expert for Instagram.
    Context: You are ALREADY inside the Private DM (Direct Message) with the prospect.
    Strategy: "High Value / Low Reach" (Tier A).
    Language: English ONLY. NO EMOJIS.
    
    PROSPECT NAME: {name}
    RAW PROFILE DATA: "{raw_profile_data}"

    INSTRUCTION:
    1. Extract the niche from the profile data (ignore numbers).
    2. Generate a message that acknowledges their high quality but mentions the undervaluation of their reach.
    3. IMPORTANT: Since we are already in the DM, DO NOT ask "Can we talk privately?". Instead, ask if they are open to feedback, ideas, or a chat about it.

    CORRECT STYLE EXAMPLES (Use these patterns):
    - "Clean aesthetic, {name}. The reach doesn't fully showcase the value here. Open to hearing a few ideas?"
    - "Strong presentation; this feels underexposed for the standard shown. Are you open to some feedback?"
    - "Very intentional content. It seems underexposed for its refinement. Would you be open to exchanging some thoughts?"
    - "Premium-level delivery, but the reach feels modest by comparison. Curious to hear your perspective on this?"

    BAD EXAMPLES (DO NOT USE):
    - "Want to DM?" (We are already in DM)
    - "Let's connect privately." (We are already private)

    RULES:
    1. Output strictly in ENGLISH.
    2. NO EMOJIS.
    3. Max 180 characters.
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.strip().replace('"', '').replace("Subject:", "")
        return clean_text
    except Exception as e:
        print(f"   [ERROR GEMINI] {e}")
        return f"{name}, clean aesthetic; the reach doesn't fully showcase the value here. Open to continue privately?"

def send_dm(driver, lead):
    print(f"Visitando: {lead['url']}")
    driver.get(lead['url'])
    time.sleep(random.uniform(5, 7))
    dismiss_popups(driver)
    
    # 1. LEER BIOGRAFÍA REAL (Texto visible)
    print("   Leyendo perfil...")
    raw_profile_text = get_profile_data(driver)
    print(f"   [DEBUG] Datos leidos: {raw_profile_text[:60]}...") # Muestra lo que leyó

    # 2. GENERAR MENSAJE
    msg = generate_ai_message(lead['name'], raw_profile_text)
    print(f"[GEMINI] Sugerencia: {msg}")
    
    wait = WebDriverWait(driver, 10)
    entrado_al_chat = False

    # 3. NAVEGACIÓN (Tres Puntos -> Enviar Mensaje)
    print("   Buscando menu Opciones...")
    try:
        xpath_dots = "//*[local-name()='svg' and (@aria-label='Opciones' or @aria-label='Options')]/ancestor::div[@role='button']"
        btn_dots = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_dots)))
        js_click(driver, btn_dots)
        print("   Click en '...' realizado.")
        
        time.sleep(2.5) 
        
        # Búsqueda agresiva del botón mensaje en el menú
        selectores_menu = [
            "//div[@role='dialog']//button[contains(., 'Enviar mensaje')]",
            "//div[@role='dialog']//div[contains(text(), 'Enviar mensaje')]",
            "//div[@role='dialog']//span[contains(text(), 'Enviar mensaje')]",
            "//div[@role='dialog']//button[contains(., 'Send message')]", 
            "//div[@role='dialog']//div[contains(text(), 'Send message')]"
        ]
        
        boton_encontrado = None
        for xpath in selectores_menu:
            try:
                elem = driver.find_element(By.XPATH, xpath)
                if elem.is_displayed():
                    boton_encontrado = elem
                    break
            except: pass
            
        if boton_encontrado:
            boton_encontrado.click()
            entrado_al_chat = True
            print("   Click en menu exitoso. Entrando al chat...")
        else:
            print("[ERROR] No se encontro el boton 'Enviar mensaje'.")

    except Exception as e:
        print(f"   [FALLO ESTRATEGIA] {e}")

    # 4. ESCRITURA
    if entrado_al_chat:
        try:
            time.sleep(random.uniform(5, 7))
            dismiss_popups(driver)

            print("   Buscando caja de texto...")
            xpath_box = "//div[@contenteditable='true'] | //div[@role='textbox']"
            box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_box)))
            
            box.click()
            time.sleep(1)
            
            print(f"   Escribiendo mensaje...")
            human_type(box, msg)
            time.sleep(random.uniform(2, 4))
            
            box.send_keys(Keys.ENTER)
            print("[OK] DM Enviado.")
            return True

        except Exception as e:
            print(f"[ERROR CHAT] {e}")
            return False
            
    return False

# ==========================================
# 5. MAIN
# ==========================================

def main():
    print(f"Iniciando Bot (Profile Reading Fix)...")
    
    account = load_account()
    if not account: return

    leads = get_leads_to_write()
    print(f"Leads pendientes: {len(leads)}")
    if not leads: return

    driver = setup_driver()
    
    try:
        login_with_cookie(driver, account)
        
        for lead in leads:
            print(f"\n--- Lead: {lead['name']} ---")
            if send_dm(driver, lead):
                update_lead_status(lead['id'])
                wait = random.uniform(120, 300) 
                print(f"Esperando {int(wait)}s...")
                time.sleep(wait)
            
    except Exception as e:
        print(f"[ERROR GLOBAL] {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    main()