import os
import google.generativeai as genai
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class ScriptRequest(BaseModel):
    script: str
    history: str

GOOGLE_API_KEY=os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel('gemini-3-flash-preview')

prompt = "Tu es un extracteur de données spécialisé pour Spotify. " \
"Analyse la requête de l'utilisateur et renvoie UNIQUEMENT un objet JSON contenant les clés 'genre' (le style musical)" \
" et 'duration' (la durée convertie en minutes sous forme d'entier). " \
"Si une information est manquante, mets 'null'. Je souhaiterais que tu renvoies également dans le JSON les ids des musiques. " \
"Si la requête de l'utilisateur n'est pas en lien avec ceci, mais qu'elle reste tout de même en lien avec l'application, " \
"réponds lui aussi normalement que possible (pas d'émoji). Si sa requête ne concerne pas l'application, dis lui " \
"'Je suis désolé, je ne peux pas répondre à votre demande'." \

