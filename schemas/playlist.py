from pydantic import BaseModel

class PlaylistBase(BaseModel):
    name : str
    genre : str
    duration : str