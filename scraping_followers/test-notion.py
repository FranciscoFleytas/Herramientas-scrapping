import requests
import datetime
import json

# TUS DATOS
NOTION_TOKEN = "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"
NOTION_DB_ID = "2b8f279cffec808ba6b3e43c7d449531"

ESTADO_TRIGGER = "Escribir"
ESTADO_FINAL = "Contactado"

def test_connection():
    # 1. BUSCAR UN LEAD
    print("1. Buscando lead en estado 'Escribir'...")
    url_query = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    payload_query = {"filter": {"property": "Estado", "status": {"equals": ESTADO_TRIGGER}}}
    
    # Nota: Si tu columna es Select, el filtro de arriba fallará y hay que cambiar "status" por "select"
    # Probamos primero genérico
    
    try:
        response = requests.post(url_query, json=payload_query, headers=headers)
        data = response.json()
        
        if "results" not in data or len(data["results"]) == 0:
            print("❌ No encontré leads con estado 'Escribir'. O el filtro falla o no hay datos.")
            # Intento con filtro Select por si acaso
            payload_select = {"filter": {"property": "Estado", "select": {"equals": ESTADO_TRIGGER}}}
            response = requests.post(url_query, json=payload_select, headers=headers)
            data = response.json()
            
        if "results" in data and len(data["results"]) > 0:
            lead = data["results"][0]
            lead_id = lead["id"]
            lead_name = lead["properties"]["Cliente"]["title"][0]["text"]["content"]
            print(f"✅ Lead encontrado: {lead_name} (ID: {lead_id})")
            
            # 2. INTENTAR ACTUALIZAR
            print(f"2. Intentando cambiar estado a '{ESTADO_FINAL}'...")
            update_lead_status(lead_id)
            
        else:
            print("❌ Sigo sin encontrar leads. Revisa que el token tenga acceso a la DB y que haya gente en 'Escribir'.")
            print(response.text)

    except Exception as e:
        print(f"Error: {e}")

def update_lead_status(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    now_iso = datetime.datetime.now().isoformat()
    
    # Probamos Payload STATUS
    payload = {
        "properties": {
            "Estado": { "status": { "name": ESTADO_FINAL } },
            "Ultimo Mensaje": { "date": { "start": now_iso } }
        }
    }
    
    res = requests.patch(url, json=payload, headers=headers)
    if res.status_code == 200:
        print("✅ ÉXITO: Se actualizó como propiedad STATUS.")
    else:
        print(f"⚠️ Falló como STATUS ({res.status_code})... Probando SELECT.")
        # Probamos Payload SELECT
        payload = {
            "properties": {
                "Estado": { "select": { "name": ESTADO_FINAL } },
                "Ultimo Mensaje": { "date": { "start": now_iso } }
            }
        }
        res2 = requests.patch(url, json=payload, headers=headers)
        if res2.status_code == 200:
            print("✅ ÉXITO: Se actualizó como propiedad SELECT.")
        else:
            print("❌ ERROR FINAL. Respuesta de Notion:")
            print(res2.text)

if __name__ == "__main__":
    test_connection()