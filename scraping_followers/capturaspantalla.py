import time
import os
import json
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from docx import Document
from docx.shared import Mm

# --- CONFIGURACIÓN ---
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
WINDOW_WIDTH = 414
WINDOW_HEIGHT = 896

# --- RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')
INPUT_TXT_FILE = os.path.join(SCRIPT_DIR, 'perfiles.txt')
BASE_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "SCREENSHOTS_MOBILE")

def setup_mobile_driver():
    options = uc.ChromeOptions()
    options.add_argument(f'--user-agent={MOBILE_UA}')
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # OPTIMIZACIÓN 1: Carga 'eager' (ansiosa). No espera assets pesados.
    options.page_load_strategy = 'eager'
    
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
    driver.set_window_size(WINDOW_WIDTH, WINDOW_HEIGHT)
    return driver

def load_account():
    if os.path.exists(CUENTAS_FILE):
        with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                return data[0] 
    return None

def load_target_profiles():
    if not os.path.exists(INPUT_TXT_FILE):
        print(f"[ERROR] Falta archivo: {INPUT_TXT_FILE}")
        return []
    with open(INPUT_TXT_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def login_with_cookie(driver, account):
    print(f"--- Logueando como {account['user']}... ---")
    driver.get("https://www.instagram.com/404")
    # Espera corta para asegurar que el navegador inició contexto
    time.sleep(1) 
    driver.add_cookie({
        'name': 'sessionid',
        'value': account['sessionid'],
        'domain': '.instagram.com',
        'path': '/',
        'secure': True,
        'httpOnly': True
    })
    driver.get("https://www.instagram.com/")
    # Espera explícita para saber que el login cargó (busca el nav bar o stories)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//main")))
    except:
        time.sleep(2) # Fallback

def clean_interface(driver):
    """Limpieza rápida de popups comunes."""
    try:
        # Timeout muy corto (1s) para no perder tiempo buscando si no existen
        WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Ahora no')]"))
        )
        # Si encuentra algo, lo cierra
        xpaths = ["//button[contains(text(), 'Not Now')]", "//button[contains(text(), 'Ahora no')]", "//button[contains(text(), 'Cancel')]"]
        for path in xpaths:
            btns = driver.find_elements(By.XPATH, path)
            for btn in btns:
                driver.execute_script("arguments[0].click();", btn)
    except: 
        pass # Si no hay popup, sigue inmediatamente

def crear_carpeta_sesion():
    if not os.path.exists(BASE_OUTPUT_DIR):
        os.makedirs(BASE_OUTPUT_DIR)
    i = 1
    while True:
        folder_name = os.path.join(BASE_OUTPUT_DIR, f"capturas {i}")
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            return folder_name
        i += 1

def capture_profile_views(driver, username, save_folder):
    print(f" > {username}", end=" ") # Print en línea para limpiar consola
    driver.get(f"https://www.instagram.com/{username}/")
    
    captured_images = []
    user_folder = os.path.join(save_folder, username)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    try:
        # OPTIMIZACIÓN 2: Espera Explícita Inteligente
        # Espera máximo 5s a que aparezca la foto de perfil o header. 
        # Si carga en 0.5s, avanza inmediatamente.
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.TAG_NAME, "header"))
        )
        
        # Limpieza rápida (opcional, suele no ser necesaria en cada perfil si ya te logueaste)
        # clean_interface(driver) 

        # Captura 1: Header
        path_header = os.path.join(user_folder, "01_header.png")
        driver.save_screenshot(path_header)
        captured_images.append(path_header)
        print(f"| Foto 1", end=" ")

        # Captura 2: Grid 1
        driver.execute_script(f"window.scrollBy(0, {WINDOW_HEIGHT * 0.6});") 
        time.sleep(1.2) # OPTIMIZACIÓN 3: Reducido de 1.5 a 0.8
        
        path_grid = os.path.join(user_folder, "02_grid.png")
        driver.save_screenshot(path_grid)
        captured_images.append(path_grid)
        print(f"| Foto 2", end=" ")

        # Captura 3: Grid 2
        driver.execute_script(f"window.scrollBy(0, {WINDOW_HEIGHT * 0.6});")
        time.sleep(1.2) # Reducido
        
        path_grid_2 = os.path.join(user_folder, "03_grid_more.png")
        driver.save_screenshot(path_grid_2)
        captured_images.append(path_grid_2)
        print(f"| Foto 3 | OK")

    except Exception as e:
        print(f"| ERROR: {e}")

    return captured_images

def generate_word_report(session_folder, data_map):
    print("\n--- Generando Word A3 ---")
    doc = Document()
    
    section = doc.sections[0]
    section.page_width = Mm(297)
    section.page_height = Mm(420)
    section.left_margin = Mm(15)
    section.right_margin = Mm(15)
    section.top_margin = Mm(15)
    section.bottom_margin = Mm(15)

    doc.add_heading('Reporte de Perfiles Instagram', 0)

    for username, images in data_map.items():
        doc.add_heading(f"Perfil: {username}", level=1)
        if len(images) > 0:
            table = doc.add_table(rows=1, cols=3)
            table.autofit = True
            for i, img_path in enumerate(images):
                if i < 3 and os.path.exists(img_path):
                    cell = table.cell(0, i)
                    paragraph = cell.paragraphs[0]
                    run = paragraph.add_run()
                    run.add_picture(img_path, width=Mm(85))
        doc.add_page_break()
    
    report_path = os.path.join(session_folder, "Reporte_A3_Completo.docx")
    doc.save(report_path)
    print(f"✅ DOC GUARDADO")

def generar_txt_resumen(session_folder, profiles_list):
    txt_path = os.path.join(session_folder, "lista_perfiles.txt")
    try:
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("LISTA DE PERFILES ANALIZADOS\n")
            for perfil in profiles_list:
                f.write(f"{perfil}\n")
        print(f"✅ TXT GUARDADO")
    except Exception as e:
        print(f"Error TXT: {e}")

def main():
    account = load_account()
    if not account: return

    target_profiles = load_target_profiles()
    if not target_profiles: return

    current_session_folder = crear_carpeta_sesion()
    driver = setup_mobile_driver()
    session_data = {}

    try:
        login_with_cookie(driver, account)
        
        for user in target_profiles:
            images = capture_profile_views(driver, user, current_session_folder)
            session_data[user] = images
            # TIEMPO DE ESPERA ENTRE PERFILES
            # Se ha reducido, pero se mantiene un mínimo aleatorio para evitar ban.
            # Antes: 2-4s. Ahora: 1.0-2.0s.
            time.sleep(random.uniform(1.0, 2.0)) 
        
        generate_word_report(current_session_folder, session_data)
        generar_txt_resumen(current_session_folder, session_data.keys())
            
    except Exception as e:
        print(f"Error global: {e}")
    finally:
        driver.quit()
        print("\n" + "="*40 + "\nPROCESO FINALIZADO\n" + "="*40)

if __name__ == "__main__":
    main()