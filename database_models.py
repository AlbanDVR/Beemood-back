from sqlalchemy import Column, String, Date, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base 

#les noms de tous les attributs et des noms des tables sont en minuscule car postgres les enregistre de cette manière

class MusicService(Base):
    __tablename__ = "musicservices" 

    name = Column("name", String(255), primary_key=True)

class Users(Base):
    __tablename__ = "users"

    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    spotify_user_id = Column("spotifyuserid", String, nullable=True)
    spotify_access_token = Column("spotifyaccesstoken", String, nullable=True)
    spotify_refresh_token = Column("spotifyrefreshtoken", String, nullable=True)
    auth_token = Column("authtoken", String, nullable=True)
    # server_default permet d'utiliser le DEFAULT CURRENT_DATE de Postgres
    join_time = Column("jointime", Date, server_default=func.current_date())

class Playlist(Base):
    __tablename__ = "playlists"

    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    title = Column("title", String(255))

    tracks = Column("tracks", ARRAY(String))
    
    # Clés étrangères
    author_id = Column("author", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    service_name = Column("musicservice", String(255), ForeignKey("musicservices.name", ondelete="SET NULL"))
