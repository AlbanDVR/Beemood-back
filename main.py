from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from dotenv import load_dotenv
import os
import base64
import httpx

from schemas.user import UserBase

from database import engine, get_db, Base
from database_models import MusicService,User,Playlist
from schemas.user import UserBase
from sqlalchemy.orm import Session

load_dotenv(dotenv_path="dev.env")

app = FastAPI()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

@app.get("/")
def read_root():
    return " le back marche"

@app.post("/login/")
async def read_root(user: UserBase, db: Session = Depends(get_db)):
    #Depends(get_db) crée une session de base de donnée et la ferme à la fin, c'est propre à FastAPI

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
        responsePost = await client.post("https://accounts.spotify.com/api/token", data=payload, headers=headers)

    # Si on à une erreur d'appel api on la renvoie au front proprement
    if responsePost.status_code != 200:
        raise HTTPException(status_code=responsePost.status_code, detail=responsePost.json())

    # On met en json la reponse avec : access token, refresh token, etc...
    responseJsonPost = responsePost.json()

    # -------------
    
    # On construit le header avec l'authorization
    user_headers = {
            "Authorization": f"Bearer {responseJsonPost['access_token']}"
            }

    # On appel en asynchrome l'api spotify pour avoir le json
    async with httpx.AsyncClient() as client:
        responseGet = await client.get("https://api.spotify.com/v1/me", headers=user_headers)

    # On met en json la reponse avec des infos user, dont l'email
    responseJsonGet = responseGet.json()

    # -------------

    reponse = responseJsonPost | responseJsonGet

    # On returne le json de reponse avec : access token, refresh token, etc...
    return reponse
