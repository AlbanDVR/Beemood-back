from sqlalchemy import select,update
from database_models import Users, Playlists, MusicService
import time
from sqlalchemy.orm import Session


def user_connection(db:Session, api_response:str):
    """
    Met à jour la BDD avec les données renvoyées par Spotify

    db: instance en éxecution de la BDD
    api_response: json avec les donées renvoyées par spotify
    """

    #Sélection de la ligne Users dont l'id corresponds au mail du json api_response
    stmt = select(Users).where(Users.spotify_user_id == api_response.get("id"))
    user = db.execute(stmt).scalar()

    #si la ligne est None: l'utilisateur est inexistant donc on l'ajoute
    if (user == None):

        new_connection = Users(
            spotify_user_id = api_response.get("id"),
            spotify_access_token = api_response.get("access_token"),
            spotify_refresh_token = api_response.get("refresh_token"),
            spotify_expires_in = api_response.get("expires_in"),
            auth_token = api_response.get("session_token"),
            spotify_time_token_created = time.time()
        )
        #ajout de la connexion à la BDD
        db.add(new_connection)
        db.commit()

    #Si la ligne existe on met à jours le access_token et refresh_token
    else:
        stmt = (
            update(Users)
            .where(Users.spotify_user_id == api_response.get("id"))
            .values(spotify_access_token = api_response.get("access_token"),spotify_refresh_token = api_response.get("refresh_token"), auth_token = api_response.get("session_token"), spotify_expires_in = api_response.get("expires_in"), spotify_time_token_created = time.time())
        )

        #éxecution du updateF
        user = db.execute(stmt)
        db.commit()
        
    #return uuid and joined status of the user whether new or existing
    stmt = select(Users).where(Users.spotify_user_id == api_response.get("id"))
    user = db.execute(stmt).scalar()
    return user.join_time, user.id


def db_playlist_update(db: Session,response_creation_playlist, info_playlist, current_user, time, service_used):
    """
    Update of the data base  with the created playlist

    db: the database on which the requests will be done
    response_creation_playlist: json containing the informations on the playlist created
    info_playlist: schemas/ playlist type
    current_user: schemas/ user type
    time: total of ms of the tracks in the created playlist 
    service_used: the music service used (for now, only spotify is used)

    """

    stmt = select(Playlists).where(Playlists.service_name == service_used)
    name_service_used = db.execute(stmt).scalar()

    #add the music service used to the MusicService table if not already in
    if( name_service_used == None):
        new_service = MusicService(
            name = service_used
        )
        db.add(new_service)
        db.commit()
    

    new_playlist = Playlists(
            id = response_creation_playlist.get("id"),
            title = info_playlist.name,
            descr = info_playlist.genre,
            duration = time,
            redirection_service = response_creation_playlist.get("uri"),
            author_id = current_user.id,
            service_name = service_used 
        )

    db.add(new_playlist)
    db.commit()