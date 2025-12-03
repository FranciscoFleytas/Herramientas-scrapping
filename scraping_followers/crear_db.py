import os
import json
import pickle

# --- RUTA AUTOMÁTICA ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(SCRIPT_DIR, 'cuentas.json')

def find_session_id_recursive(data):
    """Busca 'sessionid' en cualquier rincón de la estructura de datos."""
    # 1. Si es un diccionario
    if isinstance(data, dict):
        # Intento directo
        if 'sessionid' in data:
            return data['sessionid']
        
        # Búsqueda en valores anidados (ej: dentro de 'cookies')
        for key, value in data.items():
            result = find_session_id_recursive(value)
            if result: return result
            
            # Caso especial: a veces Instaloader guarda cookies como objetos
            if hasattr(value, 'get_dict'): # RequestsCookieJar
                try:
                    jar = value.get_dict()
                    if 'sessionid' in jar: return jar['sessionid']
                except: pass

    # 2. Si es una lista (a veces guardan listas de cookies)
    elif isinstance(data, list):
        for item in data:
            result = find_session_id_recursive(item)
            if result: return result

    # 3. Si es un objeto complejo (InstaloaderContext)
    elif hasattr(data, '__dict__'):
        return find_session_id_recursive(data.__dict__)
    
    # 4. Si es objeto con atributo cookies directo
    elif hasattr(data, 'cookies'):
        try:
            # Intento convertir cookiejar a dict
            cookies_dict = requests.utils.dict_from_cookiejar(data.cookies)
            if 'sessionid' in cookies_dict: return cookies_dict['sessionid']
        except: 
            # Fallback manual
            try:
                if 'sessionid' in data.cookies: return data.cookies['sessionid']
            except: pass

    return None

def main():
    print(f"--- GENERADOR DE BASE DE DATOS JSON (BÚSQUEDA PROFUNDA) ---")
    print(f"Directorio: {SCRIPT_DIR}")
    
    accounts_list = []
    
    files = os.listdir(SCRIPT_DIR)
    session_files = [f for f in files if f.endswith('.session')]
    
    if not session_files:
        print("[ERROR] No se encontraron archivos .session.")
        return

    print(f"Procesando {len(session_files)} archivos...")

    for filename in session_files:
        username = filename.replace('.session', '')
        file_path = os.path.join(SCRIPT_DIR, filename)
        
        session_id = None
        
        try:
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            
            # Usamos la búsqueda profunda
            session_id = find_session_id_recursive(data)
                
        except Exception as e:
            print(f"[ERROR LECTURA] {filename}: {e}")
            continue

        if session_id:
            accounts_list.append({
                "user": username,
                "pass": "ESCRIBE_TU_CLAVE_AQUI", 
                "sessionid": session_id
            })
            print(f"[OK] {username} -> ID Encontrado ({session_id[:8]}...)")
        else:
            print(f"[FALLÓ] {username} -> No se encontró 'sessionid' en la estructura.")

    if accounts_list:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts_list, f, indent=4)

        print("\n" + "="*40)
        print(f"¡LISTO! Archivo creado: cuentas.json")
        print(f"Se recuperaron {len(accounts_list)} cuentas.")
        print("="*40)
    else:
        print("\n[CRITICO] No se pudo recuperar ninguna sesión válida.")

if __name__ == "__main__":
    main()