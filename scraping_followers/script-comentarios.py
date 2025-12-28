import time
import os
import json
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException
import google.generativeai as genai

# --- CONFIGURACION ---
# 1. LINK DEL POST
TARGET_POST_URL = "https://www.instagram.com/p/DEp92mTRRjZ/" 

# 2. API KEY
GEMINI_API_KEY = "AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g"

# --- OPCIONES ---
MODO_HEADLESS = False
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# RUTAS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

# INICIAR AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 1. UTILIDADES ANTI-BOT ROBUSTAS
# ==========================================

def human_type_robust(driver, xpath, text):
    """
    Escribe texto letra por letra, pero si el elemento se vuelve 'stale' (viejo),
    lo busca de nuevo y continua.
    """
    wait = WebDriverWait(driver, 10)
    
    # Intentamos encontrar el elemento fresco
    element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
    
    # Intentamos dar click para foco
    try:
        element.click()
    except:
        pass

    for char in text:
        try:
            element.send_keys(char)
            time.sleep(random.uniform(0.03, 0.08))
        except StaleElementReferenceException:
            # Si falla, recuperamos el elemento y reintentamos la letra
            element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
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
# 3. CONTEXTO Y COMENTARIO
# ==========================================

def get_post_context(driver):
    context = {"author": "Creator", "caption": "", "image_desc": "Visual content"}
    try:
        try:
            author_elem = driver.find_element(By.XPATH, "//header//a")
            context["author"] = author_elem.text
        except: pass

        try:
            caption_elem = driver.find_element(By.TAG_NAME, "h1")
            context["caption"] = caption_elem.text
        except: pass

        try:
            img_elem = driver.find_element(By.XPATH, "//article//img")
            alt = img_elem.get_attribute("alt")
            if alt: context["image_desc"] = alt
        except: pass
        
    except Exception as e:
        print(f"   [WARN] Contexto parcial: {e}")

    return context

def generate_ai_comment(post_context):
    prompt = f"""
    ROLE: Expert Instagram Strategist (Tier A).
    TASK: Write a comment for an Instagram post.
    POST CONTEXT:
    - Visual: "{post_context.get('image_desc')}"
    - Caption: "{post_context.get('caption')}"
    RULES:
    1. Language: ENGLISH ONLY.
    2. NO EMOJIS (Strict).
    3. Length: 1 short sentence.
    4. Connect to the visual content.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '')
    except:
        return "Clean aesthetic, the execution here is top tier."

def make_comment(driver, url):
    print(f"Visitando Post: {url}")
    driver.get(url)
    time.sleep(random.uniform(5, 7))
    dismiss_popups(driver)
    
    print("   Leyendo imagen y texto...")
    context = get_post_context(driver)
    
    comment_text = generate_ai_comment(context)
    print(f"Gemini Sugiere: {comment_text}")
    
    wait = WebDriverWait(driver, 10)

    print("   Buscando caja de comentarios...")
    
    # SELECTOR
    xpath_area = "//textarea[@aria-label='Agrega un comentario...']"
    
    try:
        # 1. ENCONTRAR (Primer intento)
        comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
        
        # 2. INTENTO DE CLICK SEGURO (Manejando Stale)
        try:
            actions = ActionChains(driver)
            actions.move_to_element(comment_box).click().perform()
        except StaleElementReferenceException:
            print("   Elemento vencido (stale) al hacer click. Refrescando...")
            comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            ActionChains(driver).move_to_element(comment_box).click().perform()

        time.sleep(1) # Esperar a que la UI reaccione al click
        
        # 3. ESCRIBIR (Usando funcion robusta que maneja Stale internamente)
        print("   Escribiendo...")
        human_type_robust(driver, xpath_area, comment_text)
        time.sleep(random.uniform(1, 2))
        
        # 4. ENTER (Manejando Stale tambien aqui)
        print("   Enviando con ENTER...")
        try:
            comment_box.send_keys(Keys.ENTER)
        except StaleElementReferenceException:
            print("   Elemento vencido al dar Enter. Refrescando...")
            comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            comment_box.send_keys(Keys.ENTER)
        
        time.sleep(4) 
        print("Comentario finalizado.")
        return True

    except Exception as e:
        print(f"Error al comentar: {e}")
        return False

# ==========================================
# 4. MAIN
# ==========================================

def main():
    print(f"Iniciando Bot Comentarios (Anti-Stale)...")
    
    account = load_account()
    if not account: 
        print("Falta archivo cuentas.json")
        return

    driver = setup_driver()
    
    try:
        login_with_cookie(driver, account)
        make_comment(driver, TARGET_POST_URL)
            
    except Exception as e:
        print(f"Error Global: {e}")
    finally:
        print("Cerrando navegador...")
        driver.quit()

if __name__ == "__main__":
    main()