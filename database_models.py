from sqlalchemy import Integer, Column, String, Date, ForeignKey, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
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
    spotify_expires_in = Column("spotifyexpiresin", Integer, nullable=True)
    spotify_time_token_created = Column("spotifytimetokencreated", TIMESTAMP, nullable=True)
    auth_token = Column("authtoken", String, nullable=True)
    # server_default permet d'utiliser le DEFAULT CURRENT_DATE de Postgres
    join_time = Column("jointime", Date, server_default=func.current_date())
    liked_playlists = relationship("PlaylistLike", back_populates="user")

class PlaylistLike(Base):
    __tablename__ = "playlist_likes"
    playlist_id = Column("playlist_id", String(255), ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    playlist = relationship("Playlists", back_populates="likes_rel")
    user = relationship("Users", back_populates="liked_playlists")

class Playlists(Base):
    __tablename__ = "playlists"

    id = Column("id", String(255), primary_key=True)
    title = Column("title", String(255))

    descr = Column("descr", String(255))
    duration = Column("duration", Integer)
    track_nb = Column("tracknb", Integer)
    redirection_service = Column("redirectionservice", String(255))
    
    # Clés étrangères
    author_id = Column("author", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    service_name = Column("musicservice", String(255), ForeignKey("musicservices.name", ondelete="SET NULL"))
    likes_rel = relationship("PlaylistLike", back_populates="playlist")

class Stat(Base):
    __tablename__ = "stat"

    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    playlist_number = Column("playlistnumber", Integer, nullable=True)
    track_number = Column("tracknumber", Integer, nullable=True)
    listening_time = Column("listeningtime", Integer, nullable=True)
    connection_number = Column("connectionnumber", Integer, nullable=True)
    favorite_genre = Column("favoritegenre", String, nullable=True)

    # foreign key
    user_id = Column("userid", UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))

class Artistes(Base):
    __tablename__ = "artistes"

    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    spotify_artiste_name = Column("spotifyartistename", String(255))
    spotify_artiste_id = Column("spotifyartisteid", String(255))
    genre = Column("genre", String(255))
    popularity = Column("popularity", String(255))

class ArtisteDansPlaylist(Base):
    __tablename__ = "artistedansplaylist"

    artist_id = Column("artistid", UUID(as_uuid=True), ForeignKey("artistes.id",ondelete="CASCADE"), primary_key=True)
    playlist_id = Column("playlistid", String(255), ForeignKey("playlists.id",ondelete="CASCADE"), primary_key=True)

