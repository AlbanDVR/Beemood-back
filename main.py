from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dotenv import load_dotenv
import os
import base64
import httpx

from schemas.user import UserBase

load_dotenv(dotenv_path="dev.env")

app = FastAPI()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

@app.get("/")
def read_root():
    return " le back marche"

@app.post("/login/")
async def read_root(user: UserBase):

    # On construit le header avec les bonnes choses : uath en base 64, et un content-type
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # On construit la demande idem : grant_type, l'access code, et le redirect uri
    payload = {
        "grant_type": "authorization_code",
        "code": user.access_code,
        "redirect_uri": REDIRECT_URI
    }

    # On appel en asynchrome l'api spotify pour avoir le json
    async with httpx.AsyncClient() as client:
        response = await client.post("https://accounts.spotify.com/api/token", data=payload, headers=headers)

    # Si on à une erreur d'appel api on la renvoie au front proprement
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    # On returne le json de reponse avec : access token, refresh token, etc...
    return response.json()
