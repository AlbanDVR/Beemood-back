from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt import PyJWTError

from dotenv import load_dotenv
import os
import base64
import httpx

from schemas.user import UserBase, LoginResponse

from database import get_db
from database_models import Users
from sqlalchemy.orm import Session
from sqlalchemy import select

from APIFeatures import user_connection


load_dotenv(dotenv_path="dev.env")

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

@app.get("/")
def health_check():
    return " le back marche"

# Preflight handler for CORS
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return {"status": "ok"}

@app.post("/login/", response_model=LoginResponse)
async def login(user: UserBase, db: Session = Depends(get_db)):
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