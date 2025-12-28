import time
import os
import json
import random
import requests
import re
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
        time.sleep(random.uniform(0.03, 0.08))

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
    options.add_argument("--lang=es-AR") 
    if MODO_HEADLESS:
        options.add_argument('--headless=new')

    driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
    driver.set_window_size(1280, 850)
    return driver

def load_account():
    if not os.path.exists(CUENTAS_FILE): return None
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
                # Obtenemos el "Nombre" de Notion, pero luego intentaremos buscar el real en IG
                name_notion = props["Cliente"]["title"][0]["text"]["content"] if props["Cliente"]["title"] else "Amigo"
                raw_url = props["URL"]["url"]
                if not raw_url: continue
                leads.append({"id": res["id"], "name": name_notion, "url": raw_url if raw_url.startswith("http") else "https://" + raw_url})
            except: continue
        return leads
    except Exception as e:
        print(f"Error Notion: {e}")
        return []

def update_lead_status(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    
    payload_status = {"properties": {"Estado": {"status": {"name": ESTADO_FINAL}}, "Ultimo Mensaje": {"date": {"start": datetime.datetime.now().isoformat()}}}}
    payload_select = {"properties": {"Estado": {"select": {"name": ESTADO_FINAL}}, "Ultimo Mensaje": {"date": {"start": datetime.datetime.now().isoformat()}}}}
    
    res = requests.patch(url, json=payload_status, headers=headers)
    if res.status_code != 200:
        requests.patch(url, json=payload_select, headers=headers)
    
    print(f"Notion actualizado: {ESTADO_FINAL}")

# ==========================================
# 4. EXTRACCIÓN DE DATOS REALES (NUEVO)
# ==========================================

def get_real_name_and_bio(driver, fallback_name):
    """
    Extrae el Nombre Real (Display Name) y la Bio usando Meta Tags.
    Esto evita usar el @usuario.
    """
    real_name = fallback_name
    bio_text = "Emprendedor"

    try:
        # 1. INTENTO DE NOMBRE REAL VIA META TAG (El más seguro)
        # Formato usual: "Nombre Real (@usuario) • Instagram..."
        meta_title = driver.find_element(By.XPATH, "//meta[@property='og:title']").get_attribute("content")
        
        if "(" in meta_title:
            # Cortamos antes del parentesis del usuario
            extracted_name = meta_title.split('(')[0].strip()
            # Si el nombre extraido no esta vacio y no es generico, lo usamos
            if extracted_name and "Instagram" not in extracted_name:
                real_name = extracted_name
    except: 
        pass

    try:
        # 2. EXTRAER BIO
        bio_text = driver.find_element(By.XPATH, "//meta[@property='og:description']").get_attribute("content")
    except: 
        pass

    return real_name, bio_text

# ==========================================
# 5. GEMINI & SENDING
# ==========================================

def generate_ai_message(real_name, bio_text):
    prompt = f"""
    Objetivo: Mensaje de networking Instagram (DM).
    Prospecto (Nombre Real): {real_name}.
    Bio: "{bio_text}".
    
    INSTRUCCIONES CLAVE DE ESTILO:
    1. Usa el PRIMER NOMBRE de la persona (ej: si es "Juan Perez", di "Juan"). Si el nombre es una marca, úsalo tal cual.
    2. Usa oraciones completas y fluidas.
    3. Usa comas (,) para conectar las ideas.
    4. Estructura obligatoria: "[Nombre] you have [Elogio Completo], [Observación] | [Pregunta Completa]?"
    5. Debes generar el mensaje en DOS PARTES separadas por el simbolo "|".

    REGLAS:
    - IDIOMA: Inglés (English).
    - NO Emojis.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '')
    except:
        return f"{real_name} you have powerful visuals | Are you open to sharing some ideas?"

def clean_message_part(text):
    text = text.strip()
    if text.endswith(','): text = text[:-1]
    if text: text = text[0].upper() + text[1:]
    return text

def send_dm(driver, lead):
    print(f"Visitando: {lead['url']}")
    driver.get(lead['url'])
    time.sleep(random.uniform(5, 7))
    dismiss_popups(driver)
    
    # --- NUEVA LÓGICA DE NOMBRE ---
    # Obtenemos el nombre REAL del perfil, no el de Notion ni el usuario
    real_name, bio_text = get_real_name_and_bio(driver, lead['name'])
    
    print(f"   Identificado: {real_name} (Bio: {bio_text[:30]}...)")

    # Generamos mensaje con el nombre real
    full_msg = generate_ai_message(real_name, bio_text)
    
    raw_parts = full_msg.split('|')
    mensajes_a_enviar = [clean_message_part(p) for p in raw_parts if p.strip()]
    
    print(f"Gemini: {mensajes_a_enviar}")
    
    wait = WebDriverWait(driver, 8)
    entrado_al_chat = False

    # --- ESTRATEGIA 1: BARRIDO ---
    print("   Buscando boton visible 'Mensaje'...")
    posibles_botones = [
        "//div[text()='Mensaje']", "//div[text()='Enviar mensaje']", "//div[text()='Message']",
        "//button[contains(., 'Mensaje')]", "//button[contains(., 'Message')]", "//div[@role='button'][contains(., 'Mensaje')]"
    ]
    
    boton_directo = None
    for xpath in posibles_botones:
        try:
            elementos = driver.find_elements(By.XPATH, xpath)
            for el in elementos:
                if el.is_displayed():
                    boton_directo = el
                    break
            if boton_directo: break
        except: pass
        
    if boton_directo:
        try:
            boton_directo.click()
            entrado_al_chat = True
            print("   Click directo exitoso.")
        except:
            js_click(driver, boton_directo)
            entrado_al_chat = True
    else:
        print("   No se encontro boton visible directo.")

    # --- ESTRATEGIA 2: TRES PUNTOS ---
    if not entrado_al_chat:
        print("   Intentando estrategia Tres Puntos...")
        try:
            xpath_dots = "//*[local-name()='svg' and (@aria-label='Opciones' or @aria-label='Options')]/ancestor::div[@role='button']"
            btn_dots = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_dots)))
            js_click(driver, btn_dots)
            time.sleep(1.5) 
            
            menu_xpath = "//div[@role='dialog']//div[contains(text(), 'Enviar') or contains(text(), 'Message') or contains(text(), 'Mensaje')]"
            btn_menu = driver.find_element(By.XPATH, menu_xpath)
            btn_menu.click()
            entrado_al_chat = True
            print("   Entrado desde menu.")
        except Exception as e:
            print(f"   Fallo Tres Puntos: {e}")

    # --- FASE DE ESCRITURA ---
    if entrado_al_chat:
        try:
            time.sleep(random.uniform(4, 6))
            dismiss_popups(driver)

            print("   Buscando chat...")
            xpath_box = "//div[@contenteditable='true'] | //div[@role='textbox']"
            box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_box)))
            
            try: box.click()
            except: js_click(driver, box)
            time.sleep(1)
            
            for i, parte in enumerate(mensajes_a_enviar):
                print(f"   Escribiendo parte {i+1}...")
                human_type(box, parte)
                time.sleep(0.5) 
                box.send_keys(Keys.ENTER)
                
                if i < len(mensajes_a_enviar) - 1:
                    tiempo_pensar = random.uniform(2.5, 4.5)
                    print(f"   Pausa natural ({int(tiempo_pensar)}s)...")
                    time.sleep(tiempo_pensar)
            
            print("DM Completo Enviado.")
            return True

        except Exception as e:
            print(f"Error chat: {e}")
            return False
            
    return False

# ==========================================
# 6. MAIN
# ==========================================

def main():
    print(f"Iniciando Bot V11 (Real Name Extraction)...")
    
    account = load_account()
    if not account: return

    leads = get_leads_to_write()
    print(f"Leads pendientes: {len(leads)}")
    if not leads: return

    driver = setup_driver()
    
    try:
        login_with_cookie(driver, account)
        
        for lead in leads:
            print(f"\n--- Lead ID: {lead['id']} ---")
            if send_dm(driver, lead):
                update_lead_status(lead['id'])
                wait = random.uniform(20, 30) 
                print(f"Esperando {int(wait)}s...")
                time.sleep(wait)
            
    except Exception as e:
        print(f"Error Global: {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    main()