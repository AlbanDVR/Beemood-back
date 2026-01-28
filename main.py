
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt import PyJWTError
import random
import time

from dotenv import load_dotenv
import os
import base64
import httpx
import json

from schemas.user import UserBase, LoginResponse
from schemas.playlist import PlaylistBase

from database import get_db
from database_models import Users, Playlists, PlaylistLike, Stat
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.sql import func

from APIFeatures import user_connection, db_playlist_update
from gemini_api import ScriptRequest, model

from math import *
from collections import Counter

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

async def refresh_token(db : Session, current_user: Users):

    time_expires_in = current_user.spotify_expires_in
    time_create_token = current_user.spotify_time_token_created

    if time_create_token + time_expires_in < time.time():

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

async def creation_ajout_playlist(db : Session, current_user: Users, info_playlist: PlaylistBase, tracks_uri, duration_total, stats_track_number):

    async with httpx.AsyncClient() as client:

        # ----- APPEL SPOTIFY - Création Playlist -----

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


        # ----- APPEL SPOTIFY - Ajout dans la  Playlist -----

        headers = {
            "Authorization": f"Bearer {current_user.spotify_access_token}",
            "Content-Type": "application/json"
        }

        if not tracks_uri:
            raise HTTPException(401, "Erreur, pas de track trouvé")

        payload = {
            "position": 0,
            "uris": tracks_uri
        }

        response_ajout_playlist = await client.post(f"https://api.spotify.com/v1/playlists/{response_creation_playlist['id']}/tracks", json=payload, headers=headers)

        #updating the data base with the data
        db_playlist_update(db, response_creation_playlist, info_playlist, current_user, duration_total, "Spotify", stats_track_number)

        # Si on à une erreur d'appel api on la renvoie au front proprement
        if response_ajout_playlist.status_code not in [200, 201]:
            raise HTTPException(status_code=response_ajout_playlist.status_code, detail=response_ajout_playlist.json())

    return "ok"

@app.get("/")
def health_check():
    return " le back marche"

#Gestion des requêtes CORS OPTIONS
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
async def recuperation_playlist(info_playlist: PlaylistBase, current_user: Users = Depends(get_current_user), db: Session = Depends(get_db)):

    await refresh_token(db, current_user)

    async with httpx.AsyncClient() as client:

        # ----- APPEL SPOTIFY - Get des tracks -----

        stats_track_number = 0

        # Appel titre liké 15%
        timer_like = 0
        offset = 0
        uri_like_genre = []
        reste_tracks = True
        while timer_like < int(info_playlist.duration) * 0.15 and reste_tracks == True:

            # Appelle des tracks dans les titre likés
            headers = {
                "Authorization": f"Bearer {current_user.spotify_access_token}"
            }
            params = {
                "limit": 50,
                "offset": offset
            }
            offset += 50

            response_like = await client.get("https://api.spotify.com/v1/me/tracks", params=params, headers=headers)
            if response_like.status_code not in [200, 201]:
                raise HTTPException(status_code=response_like.status_code)

            response_like = response_like.json()["items"]

            if len(response_like) < 50: # On vérifie que il reste des musiques
                reste_tracks = False

            # Récupérer les artistes des tracks
            artistes_id = []
            for i in range(len(response_like)): # Parcours toutes les tracks
                for j in range(len(response_like[i]["track"]["artists"])): # On parcours tous les artistes d'une track
                    artistes_id.append(response_like[i]["track"]["artists"][j]["id"]) #On récupère les ids de tous les artistes

            # Check des genres des artistes
            reponse_artistes_genre = []
            for i in range(ceil(len(artistes_id)/50)): # On fait des appels get pour l'artiste en fonction du nombre d'artistes
                params = {
                    "ids": ",".join(artistes_id[:50])
                }
                artistes_id = artistes_id[50:] # On réduit la liste des 50 premiers utilisés

                response_artistes = await client.get("https://api.spotify.com/v1/artists", params=params, headers=headers)
                if response_artistes.status_code not in [200, 201]:
                    raise HTTPException(status_code=response_artistes.status_code)

                reponse_artistes_genre.extend(response_artistes.json()["artists"]) #On ajoute la liste d'artistes

            artists_genre = []
            for i in range(len(reponse_artistes_genre)): #On parcours tous les artistes des tracks
                if any(info_playlist.genre in g.lower() for g in reponse_artistes_genre[i]["genres"]) and reponse_artistes_genre[i]["id"] not in artists_genre:
                    artists_genre.append(reponse_artistes_genre[i]["id"]) #On rajoute si il est du bon genre et qu'il n'est pas déjà dans la liste

            # Filtre des tracks liké par genre (via artistes)
            tracks_like_genre = []
            for i in range(len(response_like)): # On traverse toutes les tracks likés
                #Récupère les artistes de la track
                artists_current = []
                for j in range(len(response_like[i]["track"]["artists"])): # Pour chaque tracks on récupère ces artistes
                    artists_current.append(response_like[i]["track"]["artists"][j]["id"])

                if any(item in artists_current for item in artists_genre): # On regarde si c'est un artiste du bon genre
                    tracks_like_genre.append(response_like[i]["track"])

            i = 0
            while i < len(tracks_like_genre) and timer_like < int(info_playlist.duration) * 0.15 :
                duration_track = tracks_like_genre[i]["duration_ms"]
                if duration_track < 480000 and tracks_like_genre[i]["popularity"] > 50: # 8 minutes
                    uri_like_genre.append(tracks_like_genre[i]["uri"])
                    timer_like += duration_track
                    stats_track_number += 1
                i += 1

        # Appel titre spotify
        offset = 0
        timer_spot = 0
        uri_spot_genre = []
        while timer_spot < int(info_playlist.duration) - timer_like and offset < 1000 - 50:

            headers = {
                "Authorization": f"Bearer {current_user.spotify_access_token}"
            }

            params = {
                "q": f"genre:\"{info_playlist.genre}\"",
                "type": "track",
                "offset": offset,
                "limit": 50
            }

            offset += 50

            response = await client.get("https://api.spotify.com/v1/search", params=params, headers=headers)

            # Si on à une erreur d'appel api on la renvoie au front proprement
            if response.status_code not in [200, 201]:
                raise HTTPException(status_code=response.status_code)

            all_track = response.json()["tracks"]["items"]

            # Récupération des tracks en fonction du temps
            random.shuffle(all_track)

            i = 0
            while i < len(all_track) and timer_spot < int(info_playlist.duration) - timer_like :
                duration_ms = all_track[i]["duration_ms"]
                if duration_ms < 480000 and all_track[i]["popularity"] > 50: # 8 minutes
                    uri_spot_genre.append(all_track[i]["uri"])
                    timer_spot += duration_ms
                    stats_track_number += 1
                i += 1

        tracks_total = uri_spot_genre + uri_like_genre
        random.shuffle(tracks_total)

        timer_total = timer_spot + timer_like

        await creation_ajout_playlist(db, current_user, info_playlist,tracks_total, timer_total, stats_track_number)

@app.get("/playlist")
async def get_playlists(
    source: str = "beemood",
    limit: int = 10,
    start: int = 0,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère les playlists (avec pagination) selon la source spécifiée:
    - beemood: playlists créées par l'utilisateur (default)
    - spotify: playlists de l'utilisateur sur Spotify
    - mostliked: playlists les plus likées
    """

    if source == "spotify":
        await refresh_token(db, current_user)

        headers = {
            "Authorization": f"Bearer {current_user.spotify_access_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.spotify.com/v1/me/playlists?limit={limit}&offset={start}",
                headers=headers
            )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()

    elif source == "mostliked":
        # Récupérer les playlists triées par nombre de likes
        stmt = (
            select(Playlists, func.count(PlaylistLike.user_id).label('like_count'))
            .join(Users, Playlists.author_id == Users.id)
            .outerjoin(Playlists.likes_rel)
            .group_by(Playlists.id)
            .order_by(func.count(PlaylistLike.user_id).desc())
            .offset(start)
            .limit(limit)
        )
        results = db.execute(stmt).all()

        # Récupérer les playlists déjà likées par l'utilisateur courant
        user_liked_ids = {
            like.playlist_id
            for like in db.query(PlaylistLike.playlist_id).filter(
                PlaylistLike.user_id == current_user.id
            ).all()
        }

        # Construire la réponse enrichie
        return [
            playlist.__dict__ |
            {
                "like_count": like_count,
                "liked": playlist.id in user_liked_ids
            }
            for playlist, like_count in results
        ]

    elif source == "beemood":
        beemood_playlists = db.query(Playlists).filter(
            Playlists.author_id == current_user.id
        ).order_by(Playlists.id.asc()).offset(start).limit(limit).all()
        return beemood_playlists

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source parameter. Must be 'beemood', 'spotify', or 'mostliked'"
        )

@app.post("/playlist/{playlist_id}/like")
async def like_playlist(
    playlist_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permet à l'utilisateur courant de liker une playlist spécifiée par son ID.
    """
    # Vérifier si la playlist existe
    playlist = db.query(Playlists).filter(Playlists.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Vérifier si l'utilisateur a déjà liké cette playlist
    existing_like = db.query(PlaylistLike).filter(
        PlaylistLike.playlist_id == playlist_id,
        PlaylistLike.user_id == current_user.id
    ).scalar()

    if existing_like:
        raise HTTPException(status_code=400, detail="Playlist already liked by the user")

    # Créer un nouveau like
    new_like = PlaylistLike(
        playlist_id=playlist_id,
        user_id=current_user.id
    )
    db.add(new_like)
    db.commit()

    return {"detail": "Playlist liked successfully"}

@app.delete("/playlist/{playlist_id}/like")
async def unlike_playlist(
    playlist_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permet à l'utilisateur courant de retirer son like d'une playlist spécifiée par son ID.
    """
    # Vérifier si le like existe
    existing_like = db.query(PlaylistLike).filter(
        PlaylistLike.playlist_id == playlist_id,
        PlaylistLike.user_id == current_user.id
    ).scalar()

    if not existing_like:
        raise HTTPException(status_code=404, detail="Like not found for the user on this playlist")

    # Supprimer le like
    db.delete(existing_like)
    db.commit()

    return {"detail": "Playlist unliked successfully"}


@app.delete("/playlist/{playlist_id}/delete")
async def delete_playlist(
    playlist_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows the user to delete a playlist
    """

    #checking the compliance of the user with the playlist ID
    playlist_delete = db.query(Playlists).filter(
        Playlists.author_id == current_user.id,
        Playlists.id == playlist_id,
    ).scalar()

    if not playlist_delete:
        raise HTTPException(status_code=403, detail="Playlist doesn't belong to user")


    #deleting the row of the playlist table
    db.delete(playlist_delete)
    db.commit()

    return {"detail": "Playlist deleted successfully"}
    
@app.post("/generate")
async def generate_response(request: ScriptRequest, current_user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    # On construit la requête : on fournit d'abord les instructions, puis ensuite le texte à analyser
    prompt = "Ton nom est Ernest. Tu es un assistant virtuel qui aide les utilisateurs à créer des playlists Spotify en analysant leurs demandes. Tu ne peux pas répondre à des requêtes hors sujet. Tu es une abeille. Tu ajoutes des \"Bzzz \" ou des onomatopées similaires ou des emojis abeille 🐝 dans tes réponses. Tu dois guider l'utilisateur pour créer la meilleure playlist possible en fonction de ses goûts musicaux, de la durée et du nom de la playlist souhaitée. Lorsque tu as toutes les informations nécessaires, tu renvoies après ton message un objet JSON bien formé contenant les clés 'name', 'genre', 'duration' en ms et 'tracks'. La clé name doit être un string contenant le nom de la playlist, si l'utilisateur n'en donne pas, génères en un. La clé genre doit être un string contenant le ou les genres de la playlist séparés par des virgules. La clé tracks doit contenir une liste de dictionnaires contenant une clé artist (un string) et une clé title (un string). Tu ne peux pas générer de markdown, uniquement du texte. Précède l'objet JSON par le texte \"PLAYLIST_DATA:\" pour que l'application puisse le repérer facilement. Reste plutôt concis dans tes messages. L'utilisateur peut également te donner ses artistes ou titres préférés, tu peux mélanger les genres dans une playlist ou l'utilisateur peut te demander d'inclure quelque chose en particulier."
    user_input = f"Instruction:\n {prompt}\n\nHistorique de la conversation:\n {request.history}\n\nScript/Texte à analyser:\n {request.script}"
        
    #Réponse renvoyée par l'API de Gemini
    try :
        response = model.generate_content(user_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while calling Gemini API: {str(e)}")
    
    if len(response.text.split("PLAYLIST_DATA:")) >= 2:
        json_part = response.text.split("PLAYLIST_DATA:")[1].strip()
        try:
            playlist_data = json.loads(json_part)

            # Vous pouvez maintenant utiliser playlist_data['genre'], playlist_data['duration'], playlist_data['tracks']
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse playlist data from Gemini response")

        async with httpx.AsyncClient() as client:

            track_uri_total = []
            for i in range(len(playlist_data["tracks"])):

                headers = {
                    "Authorization": f"Bearer {current_user.spotify_access_token}"
                }

                artist = playlist_data['tracks'][i]['artist']
                title = playlist_data['tracks'][i]['title']

                params = {
                    "q": f"track:\"{title}\" artist:\"{artist}\"",
                    "type": "track"
                }

                response_get = await client.get("https://api.spotify.com/v1/search", params=params, headers=headers)

                # Si on à une erreur d'appel api on la renvoie au front proprement
                if response_get.status_code not in [200, 201]:
                    raise HTTPException(status_code=response_get.status_code)

                response_get = response_get.json()

                if response_get["tracks"]["items"]:
                    track_uri_total.append(response_get["tracks"]["items"][0]["uri"])

            info_playlist = {
                "name": playlist_data["name"],
                "genre": playlist_data["genre"],
                "duration": str(playlist_data["duration"])
            }

            await creation_ajout_playlist(db, current_user, PlaylistBase(**info_playlist), track_uri_total, playlist_data["duration"], len(playlist_data["tracks"]))

        return {
            "data": response.text.split("PLAYLIST_DATA:")[0].strip(),
            "playlist_data": info_playlist | {
                "track_nb": len(playlist_data["tracks"])
            }
        }
    return {
            "data": response.text,
            "playlist_data": {}
    }

@app.get("/stats")
async def get_user_stats(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
  """
  Returns a json containing all the statistics of an user

  current_user: the user whose statistics are returned
  """   

  #checking the existence of the row in the stat table for the said user
  user_statistics = db.query(Stat).filter(
    Stat.user_id == current_user.id
  ).scalar()

  if not user_statistics:
      raise HTTPException(status_code=404, detail="No statistics for the user")
  
  #returning the json with statistics of the user
  return {
    "number_of_created_playlists": user_statistics.playlist_number,
    "number_of_tracks": user_statistics.track_number,
    "total_time_of_tracks": user_statistics.listening_time,
    "number_of_connections": user_statistics.connection_number,
    "most_popular_music_type": user_statistics.favorite_genre
  }

@app.get("/community/stats")
async def get_user_stats(
    db: Session = Depends(get_db)
):
    """
    Returns a json containing all the global statistics 
    """ 

    total_number_of_playlists = 0
    total_number_of_tracks = 0    
    total_time_of_tracks = 0
    total_number_of_connections = 0
    favorite_music_type = 0

    favorite_music_type_dict = {}

    all_stats = select(Stat)
    all_stats_results = db.execute(all_stats).scalars()

    for row in all_stats_results:
        total_number_of_playlists += row.playlist_number
        total_number_of_tracks += row.track_number    
        total_time_of_tracks += row.listening_time
        total_number_of_connections += row.connection_number

        if row.favorite_genre in favorite_music_type_dict.keys():
            favorite_music_type_dict[row.favorite_genre] += 1
        else:
            favorite_music_type_dict[row.favorite_genre] = 1

    favorite_music_type = next(iter(favorite_music_type_dict))
  
    for key,value in favorite_music_type_dict.items():
        if value > favorite_music_type_dict[favorite_music_type]:
            favorite_music_type = key
    
    #returning the json with statistics of the user
    return {
    "number_of_created_playlists": total_number_of_playlists,
    "number_of_tracks": total_number_of_tracks,
    "total_time_of_tracks": total_time_of_tracks,
    "number_of_connections": total_number_of_connections,
    "most_popular_music_type": favorite_music_type
    }

@app.get("/profile")
async def get_user_features(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the username, profile picture, date of join, stats
    """
    #checking the existence of the user
    user_profile = db.query(Users).filter(
    Users.id == current_user.id
    ).scalar()

    if not user_profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    #refresh the authorization token for spotify
    await refresh_token(db, current_user)

    async with httpx.AsyncClient() as client:    
        headers = {
            "Authorization": f"Bearer {current_user.spotify_access_token}",
        }

        response = await client.get(f"https://api.spotify.com/v1/users/{current_user.spotify_user_id}", headers=headers)
    
    profile_json = response.json()

    #get the user's spotify profile name
    profile_name = profile_json["display_name"]

    #get the user's spotify profile image
    profile_image = profile_json["images"]

    #handle the cases where there is no profile image
    #if the user doesn't have a profile image, the profile_image field will be set to: ""
    if profile_image == []:
        profile_image = ""    
    else:
        profile_image = profile_image[0]["url"]
    
    #get the user's join date
    join_date = user_profile.join_time

    #get the user's stats
    user_statistics = db.query(Stat).filter(
    Stat.user_id == current_user.id
    ).scalar()

    if not user_statistics:
        raise HTTPException(status_code=404, detail="No statistics for the user")
    
    return {
    "profile_displayed_name":profile_name,
    "profile_image": profile_image,
    "join_date": join_date, 
    "number_of_created_playlists": user_statistics.playlist_number,
    "number_of_tracks": user_statistics.track_number,
    "total_time_of_tracks": user_statistics.listening_time,
    "number_of_connections": user_statistics.connection_number,
    "most_popular_music_type": user_statistics.favorite_genre
  }


