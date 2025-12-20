import time
import os
import json
import random
import sys
import subprocess
import webbrowser
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fpdf import FPDF

# --- CONFIGURACIÓN ---
BATCH_SIZE = 10
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
WINDOW_WIDTH = 414
WINDOW_HEIGHT = 896
GEMINI_URL = "https://gemini.google.com/app/d483a5624d68b286?hl=es&hl=es"

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
        return []
    with open(INPUT_TXT_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

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
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//main")))
    except:
        time.sleep(2)

def expand_bio(driver):
    try:
        expand_buttons = driver.find_elements(By.XPATH, "//span[contains(text(), 'more') or contains(text(), 'más')]")
        for btn in expand_buttons:
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.5)
    except:
        pass

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
    print(f" > {username}", end=" ")
    driver.get(f"https://www.instagram.com/{username}/")
    
    captured_images = []
    user_folder = os.path.join(save_folder, username)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    try:
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "header")))
        
        expand_bio(driver)
        
        # Foto 1
        path_header = os.path.join(user_folder, "01_header.png")
        driver.save_screenshot(path_header)
        captured_images.append(path_header)
        print(f"| F1", end=" ")

        # Foto 2
        driver.execute_script(f"window.scrollBy(0, {WINDOW_HEIGHT * 0.8});") 
        time.sleep(1.5)
        path_grid = os.path.join(user_folder, "02_grid.png")
        driver.save_screenshot(path_grid)
        captured_images.append(path_grid)
        print(f"| F2", end=" ")

        # Foto 3
        driver.execute_script(f"window.scrollBy(0, {WINDOW_HEIGHT * 0.8});")
        time.sleep(1.5)
        path_grid_2 = os.path.join(user_folder, "03_grid_more.png")
        driver.save_screenshot(path_grid_2)
        captured_images.append(path_grid_2)
        print(f"| F3 | OK")

    except Exception as e:
        print(f"| ERROR: {e}")

    return captured_images

def generate_pdf_report(session_folder, data_map, batch_number):
    """
    Genera un PDF donde CADA IMAGEN ocupa UNA PAGINA entera.
    Mantiene los perfiles separados.
    """
    print(f"\n--- Generando PDF Parte {batch_number} ---")
    
    # Usamos A3 para tener alta resolución, Portrait (vertical)
    # A3 size: 297mm x 420mm
    pdf = FPDF(orientation="P", unit="mm", format="A3")
    pdf.set_auto_page_break(auto=True, margin=10)
    
    for username, images in data_map.items():
        # Iteramos sobre cada imagen del usuario
        for i, img_path in enumerate(images):
            if os.path.exists(img_path):
                pdf.add_page()
                
                # Título en la parte superior de cada página
                pdf.set_font("Helvetica", style="B", size=18)
                pdf.cell(0, 15, txt=f"{username} - Captura {i+1}", ln=True, align='C')
                
                try:
                    # Insertar imagen.
                    # Al ser capturas de móvil (alargadas), definimos la ALTURA (h) 
                    # para que quepa en la página y el ancho se ajusta solo (proporcional).
                    # Altura A3 (420) - Margen Título (20) - Margen inf (10) = ~390mm disponible.
                    # Centramos horizontalmente aprox (x=65) o dejamos x por defecto.
                    # x=65 centra una captura de iPhone típica en una hoja A3.
                    pdf.image(img_path, x=65, y=30, h=370)
                except Exception as e:
                    print(f"Error imagen PDF: {e}")

    report_path = os.path.join(session_folder, f"Reporte_Parte_{batch_number}.pdf")
    pdf.output(report_path)
    print(f"✅ PDF GUARDADO: {report_path}")

def generar_txt_tanda(session_folder, profiles_list, batch_number):
    txt_filename = f"textos_analizados_parte_{batch_number}.txt"
    txt_path = os.path.join(session_folder, txt_filename)
    try:
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"LISTA DE PERFILES - PARTE {batch_number}\n")
            f.write("====================================\n")
            for perfil in profiles_list:
                f.write(f"{perfil}\n")
        print(f"✅ TXT GUARDADO: {txt_filename}")
    except Exception as e:
        print(f"Error TXT: {e}")

def limpiar_archivos_temporales(session_folder, profiles_list):
    print("🧹 Limpiando temp...", end=" ")
    for username in profiles_list:
        user_folder = os.path.join(session_folder, username)
        if os.path.exists(user_folder):
            try:
                shutil.rmtree(user_folder)
            except: pass
    print("OK")

def main():
    account = load_account()
    if not account: return

    target_profiles = load_target_profiles()
    if not target_profiles: return

    current_session_folder = crear_carpeta_sesion()
    driver = setup_mobile_driver()
    
    try:
        login_with_cookie(driver, account)
        
        for i in range(0, len(target_profiles), BATCH_SIZE):
            current_batch = target_profiles[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            
            print(f"\n>>> LOTE {batch_num} (Perfiles {i+1}-{i+len(current_batch)})")
            
            batch_data = {} 
            for user in current_batch:
                images = capture_profile_views(driver, user, current_session_folder)
                batch_data[user] = images
                time.sleep(random.uniform(1.0, 2.0))
            
            # Generar PDF
            generate_pdf_report(current_session_folder, batch_data, batch_num)
            
            # Generar TXT
            generar_txt_tanda(current_session_folder, batch_data.keys(), batch_num)
            
            # Limpieza
            limpiar_archivos_temporales(current_session_folder, batch_data.keys())
            
            del batch_data
        
        print("\n--- Finalizando ---")
        if sys.platform.startswith('linux'):
            subprocess.Popen(['xdg-open', current_session_folder])
        webbrowser.open(GEMINI_URL)
            
    except Exception as e:
        print(f"Error global: {e}")
    finally:
        driver.quit()
        print("\n=== PROCESO FINALIZADO ===")

if __name__ == "__main__":
    main()