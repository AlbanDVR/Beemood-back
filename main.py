from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt import PyJWTError
import random
from datetime import datetime
import time

from dotenv import load_dotenv
import os
import base64
import httpx
#import google.generativeai as genai

from schemas.user import UserBase, LoginResponse
from schemas.playlist import PlaylistBase

from database import get_db
from database_models import Users, Playlists
from sqlalchemy.orm import Session
from sqlalchemy import select

from APIFeatures import user_connection, db_playlist_update

load_dotenv(dotenv_path=".env")

app = FastAPI()

# CORS configuration: allow Vite dev server by default
allowed_origins = [
    "http://127.0.0.1:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# Authentication dependency
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> Users:
    """
    Vérifie le token de session et retourne l'utilisateur authentifié.
    Le token doit être passé dans le header Authorization: Bearer <token>
    """
    token = credentials.credentials
    
    try:
        # Décoder le JWT pour récupérer l'email
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        user_email = payload.get("user_email")
        
        if user_email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
            
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    # Vérifier que le token existe dans la base de données
    stmt = select(Users).where(Users.auth_token == token)
    user = db.execute(stmt).scalar()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or token invalid")
    
    return user

async def refresh_token(db : Session,current_user: Users):
    print("--- Appel refresh token ---")

    time_expires_in = current_user.spotify_expires_in
    time_create_token = current_user.spotify_time_token_created

    if time_create_token + time_expires_in < time.time():
        print("--- Refresh Token ---")

        auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": current_user.spotify_refresh_token,
            "client_id": CLIENT_ID
        }

        async with httpx.AsyncClient() as client:
            responsePost = await client.post("https://accounts.spotify.com/api/token", data=payload, headers=headers)

        if responsePost.status_code not in [200, 201]:
            raise HTTPException(status_code=responsePost.status_code, detail=responsePost.json())
        
        responsePost = responsePost.json()

        #reconstruction de l'user
        if "refresh_token" not in responsePost:
            responsePost["refresh_token"] = current_user.spotify_refresh_token

        reponse = {
            "id" : current_user.spotify_user_id,
            "access_token" : responsePost["access_token"],
            "refresh_token" : responsePost["refresh_token"],
            "expires_in" : responsePost["expires_in"],
            "session_token" : current_user.auth_token
        }

        user_connection(db, reponse)

        # mise à jour du current_user
        current_user.spotify_access_token = reponse["access_token"]
        current_user.spotify_refresh_token = reponse["refresh_token"]
        current_user.spotify_expires_in = reponse["expires_in"]
        current_user.spotify_time_token_created = int(time.time())

        if "refresh_token" in responsePost:
            current_user.spotify_refresh_token = responsePost["refresh_token"]
        
        db.commit()
        db.refresh(current_user)
    
    else :
        print("--- No Refresh Token ---")

@app.get("/")
def health_check():
    return " le back marche"

# Exemple d'endpoint protégé
@app.get("/me")
async def get_current_user_info(current_user: Users = Depends(get_current_user)):
    """
    Endpoint protégé qui retourne les informations de l'utilisateur authentifié.
    Nécessite un Bearer token valide dans le header Authorization.
    """
    return {
        "user_id": str(current_user.id),
        "join_time": current_user.join_time
    }

# Preflight handler for CORS
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return {"status": "ok"}

@app.post("/login", response_model=LoginResponse)
async def login(user: UserBase, db: Session = Depends(get_db)):
    #Depends(get_db) crée une session de base de donnée et la ferme à la fin, c'est propre à FastAPI

    # ----- APPEL SPOTIFY - Token -----

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

    # ----- APPEL SPOTIFY - Infos Users -----
    
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
    
    #On génère notre propre token de session
    
    token = jwt.encode({"user_email": responseJsonGet['email']}, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

    reponse = responseJsonPost | responseJsonGet | {"session_token": token}

    #mise à jour de la BDD avec les données envoyées par Spotify
    joined, uuid = user_connection(db,reponse)

    # On returne le json de reponse avec : access token, refresh token, etc...
    return {
        "display_name": responseJsonGet['display_name'],
        "email": responseJsonGet['email'],
        "session_token": token,
        "external_urls": responseJsonGet['external_urls'],
        "images": responseJsonGet['images'],
        "joined": joined,
        "user_id": str(uuid)
    }

@app.post("/playlist")
async def creation_playlist(info_playlist: PlaylistBase, current_user: Users = Depends(get_current_user), db: Session = Depends(get_db)):

    await refresh_token(db, current_user)

    async with httpx.AsyncClient() as client:
        
        # ----- APPEL SPOTIFY - Création Playlist -----
        print("--Appel création playlist--")
        
        headers = {
            "Authorization": f"Bearer {current_user.spotify_access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "name": info_playlist.name,
            "public": False,
            "description": f"Playlist {info_playlist.name} - genre : {info_playlist.genre} - durée : {info_playlist.duration} - créée via Beemood"
        }

        response_creation_playlist = await client.post(f"https://api.spotify.com/v1/users/{current_user.spotify_user_id}/playlists", json=payload, headers=headers)
        
        # Si on à une erreur d'appel api on la renvoie au front proprement
        if response_creation_playlist.status_code not in [200, 201]:
            raise HTTPException(status_code=response_creation_playlist.status_code, detail=response_creation_playlist.json())
        
        response_creation_playlist = response_creation_playlist.json()

        # ----- APPEL SPOTIFY - Get des tracks -----
        print("--Appel des tracks --")

        headers = {
            "Authorization": f"Bearer {current_user.spotify_access_token}"
        }

        all_track=[]
        for i in range(5):
            params = {
                "q": f"genre{info_playlist.genre}",
                "type": "track",
                "offset": random.randint(0, 1000),
                "limit": 50
            }

            response = await client.get("https://api.spotify.com/v1/search", params=params, headers=headers)

            # Si on à une erreur d'appel api on la renvoie au front proprement
            if response.status_code not in [200, 201]:
                raise HTTPException(status_code=response.status_code)

            response = response.json()
            all_track.extend(response["tracks"]["items"])
        
        # Récupération des tracks en fonction du temps
        random.shuffle(all_track)
        
        time = 0
        i = 0
        tracks = []
        while time < int(info_playlist.duration) : 
            tracks.append(all_track[i]["uri"])
            time += all_track[i]["duration_ms"]
            i += 1
        
        # ----- APPEL SPOTIFY - Ajout dans la  Playlist -----
        print("--Appel ajout playlist--")

        headers = {
            "Authorization": f"Bearer {current_user.spotify_access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "position": 0,
            "uris": tracks
        }

        response_ajout_playlist = await client.post(f"https://api.spotify.com/v1/playlists/{response_creation_playlist['id']}/tracks", json=payload, headers=headers)
        
        #updating the data base with the data
        db_playlist_update(db, response_creation_playlist, info_playlist, current_user, time, "Spotify")

        # Si on à une erreur d'appel api on la renvoie au front proprement
        if response_ajout_playlist.status_code not in [200, 201]:
            raise HTTPException(status_code=response_ajout_playlist.status_code, detail=response_ajout_playlist.json())
        
        response_ajout_playlist = response_ajout_playlist.json()

        return "ok"

@app.get("/playlists-spotify")
async def get_spotify_playlists(current_user: Users = Depends(get_current_user)):
    print(current_user.spotify_access_token)
    headers = {
        "Authorization": f"Bearer {current_user.spotify_access_token}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.spotify.com/v1/me/playlists",
            headers=headers
        )
    responseJson = response.json()

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return responseJson

@app.get("/playlists-bdd")
def get_bdd_playlists(current_user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    beemoodPlaylists = db.query(Playlists).filter(Playlists.author_id == current_user.id).all()
    return beemoodPlaylists