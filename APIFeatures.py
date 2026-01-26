from sqlalchemy import select,update
from database_models import Users, Playlists, MusicService, Stat
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



    stmt = select(Users).where(Users.spotify_user_id == api_response.get("id"))
    result = db.execute(stmt).scalar()

    id = result.id

    stmt = select(Stat).where(Stat.user_id == id)
    result = db.execute(stmt).scalar()

    if result == None:
        new_stat = Stat(

            track_number = 0,
            listening_time = 0,
            connection_number = 1,
            playlist_number = 0,
            favorite_genre = None,

            user_id = id
        )

        db.add(new_stat)
        db.commit()

    else:

        stmt = select(Stat).where(Stat.user_id == id)
        result = db.execute(stmt).scalar()

        #create the user in the stat table
        connection_numb = result.connection_number

        connection_numb+=1

        stmt = (
            update(Stat)
            .where(Stat.user_id == id)
            .values(connection_number = connection_numb)
        )

        stat = db.execute(stmt)
        db.commit()
    
    #return uuid and joined status of the user whether new or existing
    stmt = select(Users).where(Users.spotify_user_id == api_response.get("id"))
    user = db.execute(stmt).scalar()
    return user.join_time, user.id


def db_playlist_update(db: Session,response_creation_playlist, info_playlist, current_user, time, service_used,tracks_number):
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

    # add to the database the statistics table

    stmt_user = select(Users).where(Users.spotify_user_id == current_user.spotify_user_id)
    res = db.execute(stmt_user).scalar()

    #used to link the user_id of Stat and author_id of Playlists with id of Users table
    user_id = res.id

    stmtStat = select(Stat).where(Stat.user_id == user_id)
    res = db.execute(stmtStat).scalar()

    id = res.id

    #update the stat
    current_playlist_number = res.playlist_number
    current_listening_time = res.listening_time
    current_track_number = res.track_number

    current_playlist_number+=1
    current_listening_time += time
    current_track_number += tracks_number

    #find the current favorite music type
    stmt_playlist = select(Playlists).where(Playlists.author_id == user_id)
    res = db.execute(stmt_playlist).fetchall()
    print(res)
    playlist_type = {}

    for row in res:
        if row[0].descr not in playlist_type.keys():
            playlist_type[row[0].descr] = 1
        else:
             playlist_type[row[0].descr] += 1
    

    #find the favorite music type of the user
    favorite_type = next(iter(playlist_type))

    for key,value in playlist_type.items():
        if value > playlist_type[favorite_type]:
            favorite_type = key

    favorite_type = favorite_type.lower()
    
    #add the statistics to the Stat table 
    stmt = (
            update(Stat)
            .where(Stat.id == id)
            .values(playlist_number = current_playlist_number, listening_time = current_listening_time, track_number = current_track_number, favorite_genre = favorite_type)
        )

    stat = db.execute(stmt)
    db.commit()

    



