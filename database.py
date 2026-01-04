from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#mettre dans un .env
DATABASE_URL = "postgresql://beemood:beemood@db:5432/beemood"

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