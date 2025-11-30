import time
import requests
import os
import random # Re-import necesario si se copio mal

# --- TUS DATOS ---
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = "33335"
PROXY_USER_BASE = "brd-customer-hl_23e53168-zone-residential_proxy1"
PROXY_PASS = "ei0g975bijby"

# Construir usuario
session_id = str(random.randint(10000, 99999))
proxy_user = f"{PROXY_USER_BASE}-session-{session_id}"
proxy_url = f"http://{proxy_user}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

proxies = {
    "http": proxy_url,
    "https": proxy_url
}

print(f"--- DIAGNOSTICO DE PROXY CORREGIDO ---")
print(f"Host: {PROXY_HOST}:{PROXY_PORT}")
print(f"Usuario: {proxy_user}")
print("-" * 30)

# PRUEBA 1: Sin Certificado
print("\n1. Probando conexión SIN certificado SSL...")
try:
    start = time.time()
    # Usamos verify=False para ignorar el SSL
    resp = requests.get("http://lumtest.com/myip.json", proxies=proxies, verify=False, timeout=15)
    print(f"   [EXITO] Código: {resp.status_code}")
    print(f"   [DATA] {resp.text}")
    print(f"   [TIEMPO] {time.time() - start:.2f}s")
except Exception as e:
    print(f"   [FALLO CRITICO] No hay salida a internet: {e}")

# PRUEBA 2: Con Certificado
crt_path = "brightdata_ca.crt"
# Buscamos en la carpeta actual
if not os.path.exists(crt_path):
    crt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brightdata_ca.crt")

if os.path.exists(crt_path):
    print(f"\n2. Probando conexión CON certificado ({crt_path})...")
    try:
        start = time.time()
        resp = requests.get("https://lumtest.com/myip.json", proxies=proxies, verify=crt_path, timeout=15)
        print(f"   [EXITO] Código: {resp.status_code}")
        print(f"   [DATA] {resp.text}")
    except Exception as e:
        print(f"   [FALLO SSL] El proxy funciona pero el certificado falla: {e}")
else:
    print(f"\n2. [OMITIDO] No se encontró el archivo '{crt_path}'")
    print("   Asegurate de descargarlo y ponerlo junto a este script.")

