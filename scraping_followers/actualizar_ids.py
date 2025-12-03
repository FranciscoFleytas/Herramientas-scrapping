import os
import pickle
import sys

def main():
    # --- DETECCION AUTOMATICA DE LA RUTA ---
    # Esto obtiene la carpeta exacta donde está guardado ESTE archivo .py
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    
    CUENTAS_FILE = os.path.join(SCRIPT_DIR, 'cuentas.txt')
    SESSION_DIR = SCRIPT_DIR

    print(f"--- DIAGNOSTICO DE RUTA ---")
    print(f"1. El script está en: {SCRIPT_DIR}")
    print(f"2. Buscando archivo en: {CUENTAS_FILE}")

    if not os.path.exists(CUENTAS_FILE):
        print(f"\n[ERROR FATAL] Python no encuentra 'cuentas.txt'.")
        print("Asegúrate de que el nombre del archivo sea exactamente 'cuentas.txt' (todo minúsculas).")
        return

    print(f"3. ¡Archivo encontrado! Iniciando actualización...\n")

    updated_lines = []
    
    # Leer cuentas.txt
    with open(CUENTAS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    count = 0

    for line in lines:
        line = line.strip()
        if not line: continue

        parts = line.split(':')
        username = parts[0].strip() # Quitamos espacios extra
        
        # Manejo seguro de contraseña
        password = parts[1].strip() if len(parts) > 1 else ""
        
        # Buscamos el archivo .session
        session_path = os.path.join(SESSION_DIR, f"{username}.session")
        session_id = None

        if os.path.exists(session_path):
            try:
                with open(session_path, 'rb') as sess_file:
                    data = pickle.load(sess_file)
                
                # Intentamos leer como diccionario directo o como objeto cookie
                if isinstance(data, dict) and 'sessionid' in data:
                    session_id = data['sessionid']
                elif hasattr(data, 'cookies'): 
                    session_id = data.cookies.get('sessionid')
                
            except Exception as e:
                print(f"[ERROR LEER] {username}: {e}")
        else:
            # Esto ayuda a ver si el nombre del archivo .session coincide con el usuario del txt
            print(f"[NO EXISTE] {username}.session (Verifica que el nombre de usuario sea idéntico)")

        # Reconstruir la línea
        if session_id:
            updated_lines.append(f"{username}:{password}:{session_id}\n")
            print(f"[OK] {username} -> ID Recuperado.")
            count += 1
        elif len(parts) >= 3:
            # Si ya tenía ID, lo dejamos
            updated_lines.append(line + "\n")
            print(f"[SKIP] {username} -> Ya tenía ID.")
        else:
            # Si no, lo dejamos igual
            updated_lines.append(f"{username}:{password}\n")

    # Guardar en disco
    with open(CUENTAS_FILE, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)

    print(f"\n>>> ¡LISTO! {count} cuentas actualizadas en 'cuentas.txt'.")

if __name__ == "__main__":
    main()