from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

#mettre dans un .env
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@db:5432/{os.getenv('POSTGRES_DB')}"

engine = create_engine(DATABASE_URL)
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