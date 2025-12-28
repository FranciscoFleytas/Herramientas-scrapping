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
        print("ERROR: No existe cuentas.json")
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
                name = props["Cliente"]["title"][0]["text"]["content"] if props["Cliente"]["title"] else "Amigo"
                raw_url = props["URL"]["url"]
                if not raw_url: continue
                leads.append({"id": res["id"], "name": name, "url": raw_url if raw_url.startswith("http") else "https://" + raw_url})
            except: continue
        return leads
    except Exception as e:
        print(f"Error Notion: {e}")
        return []

def update_lead_status(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    payload = {"properties": {"Estado": {"status": {"name": ESTADO_FINAL}}, "Ultimo Mensaje": {"date": {"start": datetime.datetime.now().isoformat()}}}}
    requests.patch(url, json=payload, headers=headers)
    print(f"Notion actualizado: {ESTADO_FINAL}")

# ==========================================
# 4. GEMINI & SENDING
# ==========================================

def generate_ai_message(name, bio_text):
    prompt = f"""
    Objetivo: Mensaje de networking Instagram (DM).
    Prospecto: {name}. Bio: "{bio_text}".
    INSTRUCCIONES: Saluda por nombre. Menciona algo breve de su bio. Haz una pregunta simple. NO vendas nada. Tono casual. Max 2 lineas.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '')
    except:
        return f"Hola {name}, vi tu perfil y me pareció muy interesante. ¿Cómo va todo?"

def send_dm(driver, lead):
    print(f"Visitando: {lead['url']}")
    driver.get(lead['url'])
    time.sleep(random.uniform(6, 8))
    dismiss_popups(driver)
    
    try:
        bio_text = driver.find_element(By.XPATH, "//meta[@property='og:description']").get_attribute("content")
    except: bio_text = "Emprendedor"

    msg = generate_ai_message(lead['name'], bio_text)
    print(f"Gemini: {msg}")
    
    wait = WebDriverWait(driver, 10)
    entrado_al_chat = False

    # --- ESTRATEGIA: BOTÓN DE OPCIONES (...) ---
    print("   Buscando botón de 'Opciones' (Tres Puntos)...")
    try:
        # 1. Abrir menú de tres puntos (Esto ya funcionaba)
        xpath_dots = "//*[local-name()='svg' and (@aria-label='Opciones' or @aria-label='Options')]/ancestor::div[@role='button']"
        btn_dots = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_dots)))
        js_click(driver, btn_dots)
        print("   Click en '...' realizado.")
        
        # 2. Esperar al menú
        time.sleep(2.5) 
        
        # 3. BUSQUEDA AGRESIVA DE "ENVIAR MENSAJE" (CORRECCIÓN AQUI)
        print("   Buscando opción en el menú...")
        
        # Lista de intentos: Texto en div, texto en button, texto en span
        selectores_menu = [
            "//div[@role='dialog']//button[contains(., 'Enviar mensaje')]",
            "//div[@role='dialog']//div[contains(text(), 'Enviar mensaje')]",
            "//div[@role='dialog']//span[contains(text(), 'Enviar mensaje')]",
            # Fallback en inglés
            "//div[@role='dialog']//button[contains(., 'Send message')]", 
            "//div[@role='dialog']//div[contains(text(), 'Send message')]"
        ]
        
        boton_encontrado = None
        for xpath in selectores_menu:
            try:
                elem = driver.find_element(By.XPATH, xpath)
                if elem.is_displayed():
                    boton_encontrado = elem
                    print(f"   Botón encontrado con selector: {xpath}")
                    break
            except: pass
            
        if boton_encontrado:
            boton_encontrado.click()
            entrado_al_chat = True
            print("   Click en menú exitoso. Entrando al chat...")
        else:
            print("No se encontró el texto 'Enviar mensaje' en el menú abierto.")
            # Debug rápido: imprimir qué texto hay en el diálogo
            try:
                dialog = driver.find_element(By.XPATH, "//div[@role='dialog']")
                print(f"   [DEBUG] Texto en menú: {dialog.text}")
            except: pass

    except Exception as e:
        print(f"   [FALLO ESTRATEGIA ...] {e}")

    # --- FASE DE ESCRITURA ---
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
            print("DM Enviado exitosamente.")
            return True

        except Exception as e:
            print(f"Error dentro del chat: {e}")
            return False
            
    return False

# ==========================================
# 5. MAIN
# ==========================================

def main():
    print(f"Iniciando Bot (Corrección Menú)...")
    
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
        print(f"Error Global: {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    main()