from sqlalchemy import select,update
from database_models import Users

from sqlalchemy.orm import Session


def user_connection(db:Session, api_response:str):
    """
    Met à jour la BDD avec les données renvoyées par Spotify

    db: instance en éxecution de la BDD
    api_response: json avec les donées renvoyées par spotify
    """

    #Sélection de la ligne Users dont l'id corresponds au mail du json api_response
    stmt = select(Users).where(Users.id == api_response.get("email"))
    user = db.execute(stmt).scalar()

    #si la ligne est None: l'utilisateur est inexistant donc on l'ajoute
    if (user == None):

        new_connection = Users(
            id = api_response.get("email"),
            spotify_access_token = api_response.get("access_token"),
            spotify_refresh_token = api_response.get("refresh_token")
        )
        #ajout de la connexion à la BDD
        db.add(new_connection)
        db.commit()

    #Si la ligne existe on met à jours le access_token et refresh_token
    else:
        stmt = (
            update(Users)
            .where(Users.id == api_response.get("email"))
            .values(spotify_access_token = api_response.get("access_token"),spotify_refresh_token = api_response.get("refresh_token"))
        )

        #éxecution du update
        user = db.execute(stmt)
        db.commit()