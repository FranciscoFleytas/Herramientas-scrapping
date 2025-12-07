import time
import os
import json
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from docx import Document
from docx.shared import Mm

# --- CONFIGURACIÓN MÓVIL (iPhone XR) ---
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
WINDOW_WIDTH = 414
WINDOW_HEIGHT = 896

# --- RUTAS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')
INPUT_TXT_FILE = os.path.join(SCRIPT_DIR, 'perfiles.txt') # Archivo de entrada
BASE_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "SCREENSHOTS_MOBILE")

def setup_mobile_driver():
    options = uc.ChromeOptions()
    options.add_argument(f'--user-agent={MOBILE_UA}')
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
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
    """Lee el archivo perfiles.txt línea por línea."""
    if not os.path.exists(INPUT_TXT_FILE):
        print(f"[ERROR] No se encontró el archivo: {INPUT_TXT_FILE}")
        print("Crea un archivo 'perfiles.txt' con un usuario por línea.")
        return []
    
    with open(INPUT_TXT_FILE, 'r', encoding='utf-8') as f:
        # Lee líneas, quita espacios en blanco y filtra líneas vacías
        profiles = [line.strip() for line in f if line.strip()]
    
    print(f"--- Perfiles cargados desde TXT: {len(profiles)} ---")
    return profiles

def login_with_cookie(driver, account):
    print(f"--- Logueando como {account['user']}... ---")
    driver.get("https://www.instagram.com/404")
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
    time.sleep(3)

def clean_interface(driver):
    try:
        xpaths = ["//button[contains(text(), 'Not Now')]", "//button[contains(text(), 'Ahora no')]", "//button[contains(text(), 'Cancel')]", "//div[@role='dialog']//button"]
        for path in xpaths:
            btns = driver.find_elements(By.XPATH, path)
            for btn in btns:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
    except: pass

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
    print(f" > Procesando perfil: {username}")
    driver.get(f"https://www.instagram.com/{username}/")
    time.sleep(4)
    clean_interface(driver)

    user_folder = os.path.join(save_folder, username)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    captured_images = []
    try:
        # Captura 1: Header
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        path_header = os.path.join(user_folder, "01_header.png")
        driver.save_screenshot(path_header)
        captured_images.append(path_header)
        print(f"   [FOTO] Bio capturada")

        # Captura 2: Grid 1
        driver.execute_script(f"window.scrollBy(0, {WINDOW_HEIGHT * 0.8});") 
        time.sleep(1.5)
        path_grid = os.path.join(user_folder, "02_grid.png")
        driver.save_screenshot(path_grid)
        captured_images.append(path_grid)
        print(f"   [FOTO] Grilla 1 capturada")

        # Captura 3: Grid 2
        driver.execute_script(f"window.scrollBy(0, {WINDOW_HEIGHT * 0.8});")
        time.sleep(1.5)
        path_grid_2 = os.path.join(user_folder, "03_grid_more.png")
        driver.save_screenshot(path_grid_2)
        captured_images.append(path_grid_2)
        print(f"   [FOTO] Grilla 2 capturada")

    except Exception as e:
        print(f"   [ERROR] {username}: {e}")

    return captured_images

def generate_word_report(session_folder, data_map):
    print("\n--- Generando reporte Word A3 ---")
    doc = Document()
    
    # Configuración A3
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
    print(f"✅ DOC GUARDADO: {report_path}")

def generar_txt_resumen(session_folder, profiles_list):
    txt_path = os.path.join(session_folder, "lista_perfiles.txt")
    try:
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("LISTA DE PERFILES ANALIZADOS\n")
            f.write("============================\n\n")
            for perfil in profiles_list:
                f.write(f"{perfil}\n")
        print(f"✅ TXT GUARDADO: {txt_path}")
    except Exception as e:
        print(f"Error creando TXT: {e}")

def main():
    account = load_account()
    if not account:
        print(f"Error: No se encontró {CUENTAS_FILE}")
        return

    # Cargar perfiles desde el TXT
    target_profiles = load_target_profiles()
    if not target_profiles:
        return # Termina si no hay perfiles

    current_session_folder = crear_carpeta_sesion()
    driver = setup_mobile_driver()
    session_data = {}

    try:
        login_with_cookie(driver, account)
        
        for user in target_profiles:
            images = capture_profile_views(driver, user, current_session_folder)
            session_data[user] = images
            time.sleep(random.uniform(2, 4))
        
        generate_word_report(current_session_folder, session_data)
        generar_txt_resumen(current_session_folder, session_data.keys())
            
    except Exception as e:
        print(f"Error global: {e}")
    finally:
        driver.quit()
        print("\n" + "="*40)
        print(f"PROCESO FINALIZADO")
        print("="*40 + "\n")

if __name__ == "__main__":
    main()