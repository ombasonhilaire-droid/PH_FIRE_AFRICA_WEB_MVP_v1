import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
# Utilise la clé que tu as mise dans le .env
api_key = os.getenv('PH_FIRE_AFRICA_KEY')

print(f"Tentative de connexion avec la clé : {api_key[:5]}...{api_key[-5:]}")

try:
    genai.configure(api_key=api_key)
    
    # SOLUTION : On utilise gemini-1.5-flash-latest qui est le nom le plus compatible
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    # Test simple
    response = model.generate_content("Bonjour Mwalimu, es-tu prêt pour l'Afrique ?")
    
    print("✅ SUCCÈS TOTAL !")
    print("Réponse de Mwalimu :", response.text)

except Exception as e:
    print("❌ ÉCHEC.")
    print("L'erreur réelle est :", e)