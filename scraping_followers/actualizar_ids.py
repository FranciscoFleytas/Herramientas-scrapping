import os
import pickle

# --- CONFIGURACIÓN ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.txt')
SESSION_DIR = SCRIPT_DIR 

def main():
    print(f">>> Iniciando actualización de IDs...")
    
    if not os.path.exists(CUENTAS_FILE):
        print("[ERROR] No existe cuentas.txt")
        return

    updated_lines = []
    
    # Leer cuentas.txt
    with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    count = 0

    for line in lines:
        line = line.strip()
        if not line: continue

        parts = line.split(':')
        username = parts[0].strip()
        
        # Manejo seguro de contraseña (si existe o no)
        password = parts[1].strip() if len(parts) > 1 else ""
        
        # Buscamos el archivo .session
        session_path = os.path.join(SESSION_DIR, f"{username}.session")
        session_id = None

        if os.path.exists(session_path):
            try:
                with open(session_path, 'rb') as sess_file:
                    data = pickle.load(sess_file)
                
                # LÓGICA CORREGIDA SEGÚN TU INSPECCIÓN:
                # El archivo es un diccionario directo {'sessionid': '...', ...}
                if isinstance(data, dict) and 'sessionid' in data:
                    session_id = data['sessionid']
                elif hasattr(data, 'cookies'): # Fallback por si acaso
                    session_id = data.cookies.get('sessionid')
                
            except Exception as e:
                print(f"[ERROR LEER] {username}: {e}")

        # Reconstruir la línea
        if session_id:
            # ¡ÉXITO! Escribimos la línea con los 3 datos
            updated_lines.append(f"{username}:{password}:{session_id}\n")
            print(f"[OK] {username} -> ID Recuperado ({session_id[:10]}...)")
            count += 1
        elif len(parts) >= 3:
            # Si ya tenía ID y no encontramos archivo nuevo, lo dejamos
            updated_lines.append(line + "\n")
            print(f"[SKIP] {username} -> Mantenido existente.")
        else:
            # No se encontró nada, dejamos usuario:pass
            updated_lines.append(f"{username}:{password}\n")
            print(f"[VACÍO] {username} -> No se halló sessionid en el archivo.")

    # Guardar en disco
    with open(CUENTAS_FILE, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)

    print(f"\n>>> ¡LISTO! {count} cuentas actualizadas en 'cuentas.txt'.")

if __name__ == "__main__":
    main()