import google.generativeai as genai
import os

# Pega aquí tu API KEY tal cual la tienes en el bot
GEMINI_API_KEY = "AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g" 

def test_gemini():
    print("--- PROBANDO GEMINI API ---")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        print("Enviando prompt de prueba...")
        response = model.generate_content("Hola, escribe una frase motivadora corta.")
        
        print("\n✅ ÉXITO! Respuesta recibida:")
        print(response.text)
        
    except Exception as e:
        print("\n❌ ERROR DETECTADO:")
        print(e)
        print("\nPosibles soluciones:")
        print("1. Revisa que la API KEY sea correcta.")
        print("2. Ejecuta 'pip install --upgrade google-generativeai'")
        print("3. Verifica que tu cuenta de Google Cloud tenga la API habilitada.")

if __name__ == "__main__":
    test_gemini()