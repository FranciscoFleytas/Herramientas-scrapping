import time
import os
import random
import string
import shutil 
import csv
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys

# --- CONFIGURACIÓN ---
DEFAULT_API_KEY = "9eAb7bfb9b70fef6709b315fc1708ee8" 
SMS_SERVICE_CODE = "ig" 
SMS_COUNTRY_ID = "29" # Argentina

# BRIGHT DATA
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER_BASE = "brd-customer-hl_23e53168-zone-scrapping_usser-country-ar"
PROXY_PASS = "6p7y5qv5mz4q"

CSV_FILE = "cuentas_instagram.csv"

# --- FUNCIONES DE SOPORTE ---
def save_to_csv(username, password, phone, status="OK"):
    file_exists = os.path.exists(CSV_FILE)
    try:
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            if not file_exists:
                writer.writerow(["Usuario", "Contraseña", "Telefono", "Estado"])
            writer.writerow([username, password, phone, status])
            print(f"   [GUARDADO] {username}")
    except Exception: pass

class SMSHandler:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.sms-activate.org/stubs/handler_api.php"
        self.activation_id = None
        self.phone_number = None

    def get_number(self):
        params = {'api_key': self.api_key, 'action': 'getNumber', 'service': SMS_SERVICE_CODE, 'country': SMS_COUNTRY_ID}
        try:
            print(f"   [API] Solicitando número...")
            resp = requests.get(self.url, params=params).text
            
            if "ACCESS_NUMBER" in resp:
                parts = resp.split(':')
                self.activation_id = parts[1]
                self.phone_number = parts[2]
                return self.phone_number
            elif "NO_NUMBERS" in resp:
                print(f"   [ERROR API] NO HAY STOCK.")
            elif "NO_BALANCE" in resp:
                print(f"   [ERROR API] SIN SALDO.")
            elif "BAD_KEY" in resp:
                print(f"   [ERROR API] API KEY INCORRECTA.")
            else:
                print(f"   [ERROR API]: {resp}")
            return None
        except Exception as e: 
            print(f"   [ERROR CONEXION] {e}")
            return None

    def wait_for_code(self, retries=40):
        if not self.activation_id: return None
        print(f"   --> Esperando SMS IG en {self.phone_number}...", end="", flush=True)
        for _ in range(retries):
            try:
                resp = requests.get(self.url, params={'api_key': self.api_key, 'action': 'getStatus', 'id': self.activation_id}).text
                if "STATUS_OK" in resp:
                    code = resp.split(':')[1]
                    print(f" ¡LLEGÓ! {code}")
                    return code
                elif "STATUS_WAIT_CODE" in resp:
                    print(".", end="", flush=True)
                    time.sleep(3)
                elif "STATUS_CANCEL" in resp:
                    return None
            except: time.sleep(2)
        return None

    def set_status(self, status):
        if self.activation_id:
            requests.get(self.url, params={'api_key': self.api_key, 'action': 'setStatus', 'status': status, 'id': self.activation_id})

# --- SOLUCIÓN: CARPETAS EN VEZ DE ZIP ---
def create_proxy_auth_folder(host, port, user, password, session_id):
    # --- MANIFEST V3 (ESTÁNDAR ACTUAL) ---
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 3,
        "name": "Chrome Proxy Auth V3",
        "permissions": [
            "proxy",
            "webRequest",
            "webRequestAuthProvider",
            "webRequestBlocking"
        ],
        "host_permissions": [
            "<all_urls>"
        ],
        "background": {
            "service_worker": "background.js"
        }
    }
    """
    
    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{host}",
                port: parseInt({port})
            }},
            bypassList: ["localhost"]
        }}
    }};

    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{user}-session-{session_id}",
                password: "{password}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """
    
    # Crear carpeta única
    folder_name = f'proxy_auth_{session_id}'
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    
    # Escribir archivos
    with open(os.path.join(folder_name, "manifest.json"), 'w') as f:
        f.write(manifest_json)
        
    with open(os.path.join(folder_name, "background.js"), 'w') as f:
        f.write(background_js)
        
    return folder_name

def get_ig_identity():
    NOMBRES = ["leo", "maxi", "juan", "seba", "lucas", "nico", "dani", "agustin", "fede"]
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    username = f"{random.choice(NOMBRES)}_{suffix}"
    pwd = f"IgPass.{random.randint(1000,9999)}"
    name_full = f"{random.choice(NOMBRES).capitalize()} {suffix}"
    return {"user": username, "pass": pwd, "name": name_full}

def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.1, 0.3))

def run_ig_creation(index, sms_manager):
    identity = get_ig_identity()
    session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    print(f"\n=== Instagram {index}: {identity['user']} ===")
    
    CHROME_PORTABLE = r"C:\Users\venta\Desktop\chrome-win64\chrome.exe"
    plugin_path = create_proxy_auth_folder(PROXY_HOST, PROXY_PORT, PROXY_USER_BASE, PROXY_PASS, session_id)
    
    options = uc.ChromeOptions()
    options.add_argument(f'--load-extension={os.path.abspath(plugin_path)}')
    options.add_argument('--lang=es-AR')
    options.add_argument('--no-sandbox')
    
    # --- ARMAS ANTI-BLOQUEO ---
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors=yes')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-quic') 
    options.add_argument('--disable-gpu')
    
    # MODO MÓVIL MANUAL (Pixel 7 User Agent)
    options.add_argument('--user-agent=Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36')
    
    if os.path.exists(CHROME_PORTABLE):
        print(f"   [INFO] Usando Chrome Portátil: {CHROME_PORTABLE}")
        options.binary_location = CHROME_PORTABLE
    else:
        print(f"   [ERROR] No encontré Chrome en: {CHROME_PORTABLE}")
        return

    try:
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=131)
        driver.set_window_size(412, 915) # Tamaño celular
    except Exception as e:
        print(f"[ERROR FATAL DRIVER]: {e}")
        return
    
    try:
        # 1. CALENTAMIENTO
        try:
            driver.set_page_load_timeout(10)
            driver.get("http://lumtest.com/myip.json")
            time.sleep(1)
        except: pass
        
        # 2. ENTRAR A INSTAGRAM
        print("1. Entrando a Instagram (Modo Android)...")
        driver.set_page_load_timeout(60)
        driver.get("https://www.instagram.com/accounts/emailsignup/")
        
        wait = WebDriverWait(driver, 25)
        
        # --- LOGICA MOVIL: CAMBIAR PESTAÑA A TELEFONO ---
        print("   Configurando formulario móvil...")
        try:
            # En la vista móvil, a veces hay que clickear "Número de celular"
            # Buscamos botones que contengan "celular", "Phone" o "Number"
            phone_tab = driver.find_element(By.XPATH, "//span[contains(text(), 'celular') or contains(text(), 'Phone') or contains(text(), 'Number')]")
            phone_tab.click()
            time.sleep(1)
        except:
            # Si falla, quizás ya está en la pestaña correcta o es una vista unificada
            pass

        # 3. DETECTAR INPUT CORRECTO
        try:
            # En móvil, el input suele llamarse 'phoneNumber'
            # En desktop/híbrido es 'emailOrPhone'
            # Probamos ambos
            inputs = driver.find_elements(By.NAME, "phoneNumber")
            if inputs:
                target_input_name = "phoneNumber"
            else:
                target_input_name = "emailOrPhone"
                
            email_phone_input = wait.until(EC.visibility_of_element_located((By.NAME, target_input_name)))
            print(f"   Input detectado: {target_input_name}")
            
        except:
            print("   [STUCK] No cargó el input. Refrescando...")
            driver.refresh()
            time.sleep(5)
            try:
                # Reintento post-refresh
                try: 
                    driver.find_element(By.XPATH, "//span[contains(text(), 'celular')]").click()
                    time.sleep(1)
                except: pass
                
                email_phone_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='tel' or @name='phoneNumber']")))
                print("   [RECOVERY] Cargado tras refresh.")
            except:
                print("[ERROR] Formulario no aparece.")
                driver.save_screenshot(f"debug_mobile_{index}.png")
                return
        
        # 4. COMPRAR NUMERO
        print("2. Comprando número...")
        number = sms_manager.get_number()
        if not number:
            print("[ERROR CRITICO] Sin número.")
            return

        print(f"   Número: {number}")
        
        # Limpieza por si hay prefijo automático
        email_phone_input.send_keys(Keys.CONTROL + "a")
        email_phone_input.send_keys(Keys.DELETE)
        human_type(email_phone_input, number)
        
        # Click Siguiente (Botón azul)
        try:
            # En móvil el botón suele ser azul y decir "Next" o "Siguiente"
            signup_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            signup_btn.click()
        except:
            print("[!] Error click Siguiente")
            
        # 5. DATOS RESTANTES (NOMBRE Y PASS)
        # Nota: En móvil, IG a veces pide el código SMS *antes* del nombre/pass, o al revés.
        # Vamos a detectar qué pide ahora.
        time.sleep(3)
        
        page_source = driver.page_source.lower()
        
        # CASO A: Pide confirmación SMS inmediatamente (Flow común en móvil)
        if "confirm" in page_source or "código" in page_source or "code" in page_source:
            print("3. IG pidió SMS inmediatamente...")
            confirmation_input = wait.until(EC.visibility_of_element_located((By.NAME, "confirmationCode")))
            
            code = sms_manager.wait_for_code()
            if code:
                human_type(confirmation_input, code)
                driver.find_element(By.XPATH, "//button[@type='submit']").click()
                sms_manager.set_status(6)
                print("   [EXITO] Código enviado.")
                
                # Despues del código pedirá el nombre y pass
                print("4. Llenando datos personales...")
                time.sleep(3)
                human_type(wait.until(EC.visibility_of_element_located((By.NAME, "fullName"))), identity['name'])
                human_type(driver.find_element(By.NAME, "password"), identity['pass'])
                # En este flow a veces no pide username, lo genera solo, o pide fecha
                try: driver.find_element(By.XPATH, "//button[@type='submit']").click() # Siguiente
                except: pass
                
                # Guardar save_to_csv (pero aun falta fecha)
            else:
                print("   [FAIL] Código no llegó.")
                sms_manager.set_status(8)
                return

        # CASO B: Pide Nombre/Pass primero (Flow clásico)
        else:
            print("3. Llenando datos personales primero...")
            try:
                human_type(wait.until(EC.visibility_of_element_located((By.NAME, "fullName"))), identity['name'])
                human_type(driver.find_element(By.NAME, "password"), identity['pass'])
                # En móvil a veces pide "save login info", saltar
                driver.find_element(By.XPATH, "//button[@type='submit']").click() # Siguiente
            except:
                print("   [INFO] No pidió nombre/pass aquí.")

        # 6. FECHA NACIMIENTO
        print("   Fecha Nacimiento...")
        time.sleep(4)
        try:
            # Intentamos llenar selects si existen (interfaz web)
            try:
                month_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "select[title='Month:']")))
                Select(month_elem).select_by_index(random.randint(1,12))
                Select(driver.find_element(By.CSS_SELECTOR, "select[title='Day:']")).select_by_index(random.randint(1,28))
                Select(driver.find_element(By.CSS_SELECTOR, "select[title='Year:']")).select_by_value(str(random.randint(1995, 2000)))
            except:
                # Si son spinners nativos, es difícil manipularlos ciegamente. 
                # Intentamos dar "Siguiente" a ver si tiene default.
                pass

            # Botón siguiente
            try: driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]").click()
            except: driver.find_element(By.XPATH, "//button[contains(text(), 'Siguiente')]").click()
            
        except Exception as e:
            print(f"[Info] Paso fecha: {e}")

        # 7. USERNAME (A veces lo pide al final)
        time.sleep(3)
        if "username" in driver.page_source.lower():
             print("   Eligiendo Username...")
             try:
                 driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]").click() # Aceptar sugerido
             except: pass

        # FINAL: CHECK Y GUARDADO
        time.sleep(5)
        status_acc = "CREADA" if "instagram.com/" in driver.current_url else "CHECKPOINT"
        save_to_csv(identity['user'], identity['pass'], number, status_acc)

    except Exception as e:
        print(f"[ERROR GENERAL] {e}")
        driver.save_screenshot(f"error_general_{index}.png")

    finally:
        try: driver.quit()
        except: pass
        if os.path.exists(plugin_path):
            try: shutil.rmtree(plugin_path)
            except: pass
            
def main():
    print("--- CREADOR INSTAGRAM MASSIVO (DEBUG MODE) ---")
    
    try: import distutils
    except ImportError:
        print("\n[!!!] Falta 'setuptools'. Ejecuta: pip install setuptools")
        return

    api_key_input = input(f"API Key SMS-Activate [Enter para default]: ").strip()
    api_key = api_key_input if api_key_input else DEFAULT_API_KEY
    
    sms_manager = SMSHandler(api_key)
    
    try: qty = int(input("Cantidad de cuentas: "))
    except: qty = 1
    
    for i in range(1, qty + 1):
        run_ig_creation(i, sms_manager)
        wait_sec = random.randint(10, 20)
        print(f"Esperando {wait_sec}s...")
        time.sleep(wait_sec)

if __name__ == "__main__":
    main()