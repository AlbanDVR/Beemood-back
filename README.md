# Back 

## Contenu

*   [Technologies utilisées](#technologies-utilisées)
*   [Sécurité et Authentification](#sécurité-et-authentification)
    * [Configuration de l'authentification](#️-configuration-de-lauthentification)
*   [Intelligence Artificielle](#-intelligence-artificielle)
    *   [Configuration API Google](#-configuration-api-google)
*   [Run](#run)

## Technologies utilisées 

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Postman](https://img.shields.io/badge/Postman-FF6C37?style=for-the-badge&logo=postman&logoColor=white)

* 🐍 **Python** : Choisi pour la simplicité de sa syntaxe, et aussi grâce à nos précédentes expériences sur ce langage.
* ⚡ **FastAPI** : Framework Python utilisé pour le développement de l'API et des différents endpoints.
* 🐳 **Docker** : Pour que chacun n'ait pas à installer toutes les dépendances en local.
* 🚀 **Postman** : Pour tester les endpoints de notre API.

## Sécurité et Authentification
![JWT](https://img.shields.io/badge/JWT-black?style=for-the-badge&logo=JSON%20web%20tokens)
![Spotify](https://img.shields.io/badge/Spotify-1DB954?style=for-the-badge&logo=spotify&logoColor=white)
* 🔑 **JWT (JSON Web Tokens)** : Utilisé pour sécuriser les échanges entre le client et l'API. Une fois l'utilisateur connecté, un token signé est généré pour maintenir une session sans état (stateless).
* 🎧 **OAuth 2.0 (Spotify API)** : Intégration de la pipeline d'authentification de Spotify. Les utilisateurs peuvent se connecter de manière sécurisée, ils peuvent ensuite accorder à l'application  des permissions spécifiques appelées scopes (pour accéder à leurs playlists, en créer...)

---

### ⚙️ Configuration de l'authentification

Renseignez les valeurs suivantes dans votre fichier `.env` :

```env
JWT_SECRET=votre_cle_secrete_aleatoire
SPOTIFY_CLIENT_ID=votre_client_id
SPOTIFY_CLIENT_SECRET=votre_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/auth
```
## 🤖 Intelligence Artificielle

![Gemini](https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)


* ✨ **Google Gemini API** : Notre chatbot Ernest fonctionne avec Gemini. Chaque fois que l'utilisateur envoie un message, celui-ci est transmis à Gemini, ainsi qu'un prompt afin de lui donner des instructions sur ce qu'il doit faire. Dans notre cas, nous utilisons le modèle `gemini-3flash-preview`.

---

### 🔑 Configuration API Google

Ajoutez votre clé API dans le fichier `.env` pour activer les fonctionnalités d'IA (vous pouvez en obtenir une sur le Google AI Studio):

```env
GOOGLE_API_KEY=votre_cle_api_gemini
```
## 🗄️ Base de données

![PostGreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)

* 🐘 **PostgreSQL** : 

---

### 💾 Configuration Base de Données

Dans votre fichier `.env`, configurez l'accès ainsi :

```env
POSTGRES_USER=votre_utilisateur
POSTGRES_PASSWORD=votre_mot_de_passe
POSTGRES_DB=nom_de_la_db
POSTGRES_HOST=db  # Utilisez 'db' si vous êtes dans un réseau Docker, sinon 'localhost'
POSTGRES_PORT=5432
```

## Run

Pour lancer l'application, lancer la commande `docker-compose up --build`

