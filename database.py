from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

#mettre dans un .env
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA")

connect_args = {}
if POSTGRES_SCHEMA:
    # Set the default schema for this connection (search_path)
    connect_args["options"] = f"-csearch_path={POSTGRES_SCHEMA}"

engine = create_engine(DATABASE_URL, connect_args=connect_args)
#engine permet la communication avec la base de données postgresSQL

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#création d'un modèle de session que qui sera instancié à chaque utilisation de Session()

Base = declarative_base()
#Base est une classe de base dont toutes les tables de database_models.py vont hériter.

# Dépendance pour récupérer la session DB dans chaque endpoint
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()