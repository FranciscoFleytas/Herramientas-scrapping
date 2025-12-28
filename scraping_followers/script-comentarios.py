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
TARGET_POST_URL = "https://www.instagram.com/p/DQ7JXQHDfx8/" 
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
# 1. UTILIDADES ANTI-BOT
# ==========================================

def human_type_robust(driver, xpath, text):
    wait = WebDriverWait(driver, 10)
    try:
        element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        element.click()
    except: pass

    for char in text:
        try:
            element.send_keys(char)
            time.sleep(random.uniform(0.02, 0.07))
        except StaleElementReferenceException:
            element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            element.send_keys(char)
            time.sleep(random.uniform(0.02, 0.07))

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

def load_all_accounts():
    if not os.path.exists(CUENTAS_FILE): return []
    try:
        with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list): return data
            return []
    except: return []

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
# 3. LÓGICA DE LECTURA Y GENERACIÓN DE COMENTARIO
# ==========================================

def get_post_context(driver):
    """
    Extrae la descripcion (Caption) para entender el tema del post.
    """
    context = {"caption": "", "image_desc": ""}
    try:
        # Intentamos leer el H1 que suele contener el usuario + la descripcion
        # Este es el metodo mas comun en posts individuales
        try:
            caption_elem = driver.find_element(By.TAG_NAME, "h1")
            context["caption"] = caption_elem.text
        except: 
            # Fallback: buscar dentro de la lista de items (ul) si es un Reel o vista modal
            try:
                caption_elem = driver.find_element(By.XPATH, "//div[@role='button']//span | //ul//li//span")
                if len(caption_elem.text) > 5: # Filtro basico de longitud
                    context["caption"] = caption_elem.text
            except: pass

        # Leemos el Alt Text de la imagen como respaldo
        try:
            img_elem = driver.find_element(By.XPATH, "//article//img")
            alt = img_elem.get_attribute("alt")
            if alt: context["image_desc"] = alt
        except: pass

    except: pass
    return context

def generate_ai_comment(post_context):
    
    text_angles = [
        "FOCUS: Agree strongly with the main point of the text.",
        "FOCUS: Pick a specific keyword from the caption and mention it.",
        "FOCUS: Compliment the clarity of their explanation.",
        "FOCUS: Add a short supportive statement about the topic.",
        "FOCUS: Mention how this advice is valuable for the niche.",
        "FOCUS: Minimalist agreement (3-5 words).",
        "FOCUS: Highlight the mindset behind the text.",
        "FOCUS: Express gratitude for sharing this insight.",
        "FOCUS: Relate the text to the visual quality.",
        "FOCUS: Professional acknowledgment of the strategy."
    ]
    
    common_words = ["good", "great", "nice", "love", "awesome", "amazing", "true", "agree", "thanks", "perfect"]
    forbidden = random.sample(common_words, 3)
    
    selected_angle = random.choice(text_angles)
    
    print(f"   [AI] Angulo: {selected_angle}")

    prompt = f"""
    ROLE: Expert Social Media User.
    TASK: Write a comment for an Instagram post based on its DESCRIPTION (Caption).
    
    POST CONTEXT:
    - Caption (Text written by author): "{post_context.get('caption')}"
    - Visual Context (Backup): "{post_context.get('image_desc')}"
    
    INSTRUCTION:
    1. Read the 'Caption' carefully to understand the TOPIC.
    2. Write a comment that proves you read the text.
    3. Follow this specific angle: {selected_angle}
    
    CONSTRAINTS:
    1. Language: ENGLISH ONLY.
    2. NO EMOJIS.
    3. DO NOT use these words: {forbidden}.
    4. Keep it natural and short (1 sentence).
    5. If the caption is empty, comment on the visual aesthetic instead.
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.strip().replace('"', '').replace("Comment:", "")
        return text
    except:
        return "This perspective is really valuable."

def make_comment(driver, url):
    print(f"Visitando Post: {url}")
    driver.get(url)
    time.sleep(random.uniform(5, 7))
    dismiss_popups(driver)
    
    print("   Analizando descripcion del post...")
    context = get_post_context(driver)
    
    # --- LOG DE DEPURACION (SOLICITADO) ---
    print("\n" + "="*40)
    print(f"[DEBUG] DESCRIPCION ENCONTRADA:\n{context['caption']}")
    print("="*40 + "\n")
    # --------------------------------------
    
    comment_text = generate_ai_comment(context)
    print(f"Gemini Sugiere: {comment_text}")
    
    wait = WebDriverWait(driver, 10)
    print("   Buscando caja...")
    
    xpath_area = "//textarea[@aria-label='Agrega un comentario...']"
    
    try:
        comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
        
        try:
            actions = ActionChains(driver)
            actions.move_to_element(comment_box).click().perform()
        except StaleElementReferenceException:
            comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            ActionChains(driver).move_to_element(comment_box).click().perform()

        time.sleep(1)
        
        print("   Escribiendo...")
        human_type_robust(driver, xpath_area, comment_text)
        time.sleep(random.uniform(1, 2))
        
        print("   Enviando...")
        try:
            comment_box.send_keys(Keys.ENTER)
        except StaleElementReferenceException:
            comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            comment_box.send_keys(Keys.ENTER)
        
        time.sleep(4) 
        print("Comentario enviado.")
        return True

    except Exception as e:
        print(f"Error al comentar: {e}")
        return False

# ==========================================
# 4. MAIN
# ==========================================

def main():
    print(f"Iniciando Bot (Debug Descripcion)...")
    
    accounts = load_all_accounts()
    if not accounts: 
        print("Falta archivo cuentas.json")
        return

    print(f"Cuentas cargadas: {len(accounts)}")

    for i, account in enumerate(accounts):
        print(f"==========================================")
        print(f"CUENTA {i+1}/{len(accounts)}: {account.get('user')}")
        print(f"==========================================")
        
        driver = setup_driver()
        try:
            login_with_cookie(driver, account)
            success = make_comment(driver, TARGET_POST_URL)
            
            if success:
                print(f"Exito: {account.get('user')}")
            else:
                print(f"Fallo: {account.get('user')}")
        except Exception as e:
            print(f"Error critico: {e}")
        finally:
            print("Cerrando...")
            driver.quit()
        
        if i < len(accounts) - 1:
            wait_time = random.uniform(15, 25)
            print(f"Pausa de seguridad: {int(wait_time)}s...")
            time.sleep(wait_time)

    print("--- PROCESO TERMINADO ---")

if __name__ == "__main__":
    main()