# 📖 Le Jeu du Dico

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8.0-646CFF.svg)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED.svg)](https://www.docker.com/)

Un jeu d'ambiance et de bluff multijoueur en temps réel basé sur le célèbre jeu du dictionnaire.  
Inventez les définitions les plus crédibles pour des mots rares ou oubliés de la langue française, bernez vos amis et retrouvez la véritable définition du dictionnaire !

---

## 🎯 Règles & Déroulement du Jeu

À chaque manche :

1. **🎲 Tirage du mot** : Un mot rare, technique ou méconnu est tiré au sort depuis la base du dictionnaire. Si un joueur le connaît déjà, l'hôte peut relancer le tirage.
2. **✍️ Phase d'écriture (Bluff)** : Chaque joueur invente secrètement une définition imaginaire qui semble authentique. Un compte à rebours s'écoule (configurable de 10 à 300 secondes).
3. **🗳️ Phase de vote** : Toutes les propositions inventées sont mélangées anonymement avec la **vraie définition**. Chaque joueur vote pour la définition qui lui semble être la vraie (impossible de voter pour sa propre proposition).
4. **🏆 Révélation & Points** :
   - **+1 point** si vous découvrez la vraie définition du dictionnaire.
   - **+1 point** par joueur qui s'est fait duper par votre fausse définition.
5. **👑 Podium final** : La partie s'achève au terme du nombre de manches choisi (1 à 20 manches), désignant le grand vainqueur !

---

## ✨ Fonctionnalités

- **Multijoueur temps réel (WebSockets)** : jusqu'à 10 joueurs en simultané par salon.
- **Salons personnalisables** : l'hôte configure le temps d'écriture et le nombre de manches.
- **Tolérance aux déconnexions** : reconnexion fluide sans perte de score et compte à rebours de grâce (30 s) avant retrait du joueur.
- **Dictionnaire étendu** : base de mots SQLite pré-remplie, avec script d'extraction automatique depuis le **Wiktionnaire**.
- **Authentification & Profils** : inscription / connexion sécurisée (mots de passe hachés avec bcrypt, tokens JWT).
- **Architecture conteneurisée** : prêt à être lancé en une seule commande avec Docker Compose.

---

## 🏗️ Architecture du Projet

Le projet adopte une architecture moderne découplée :

```
jeu_du_dico/
├── Dockerfile.backend           # Build multi-étape backend (uv + Python 3.12)
├── Dockerfile.frontend          # Build multi-étape frontend (Node 22 + Nginx)
├── docker-compose.yml           # Orchestration des conteneurs
├── pyproject.toml               # Dépendances backend & configuration outils
├── src/
│   ├── backend/
│   │   ├── core/                # Base de données, sécurité JWT, dépendances, constantes
│   │   ├── game/                # Machine à états (game_manager), WebSockets (connection_manager)
│   │   ├── models/              # Modèles SQLAlchemy (Word, User) & Schémas Pydantic
│   │   ├── routers/             # Endpoints REST (/api/auth) et WebSockets (/ws/rooms)
│   │   ├── scripts/             # Scripts utilitaires (seed_db, fetch_wiktionary)
│   │   ├── services/            # Logique métier (user_service, word_service)
│   │   ├── tests/               # Suite de tests unitaires et d'intégration (pytest)
│   │   └── main.py              # Point d'entrée de l'application FastAPI
│   └── frontend/
│       ├── nginx.conf           # Configuration proxy inverse pour Nginx
│       ├── package.json         # Dépendances React & Vite
│       └── src/
│           ├── App.jsx          # Interface principale (Lobby, Jeu, Révélation)
│           ├── socket.js        # Client WebSocket temps réel
│           └── ...
```

---

## 🚀 Démarrage Rapide

### Option 1 : Avec Docker Compose (Recommandé)

Prérequis : [Docker](https://www.docker.com/) & Docker Compose installés.

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/<votre-utilisateur>/jeu_du_dico.git
   cd jeu_du_dico
   ```

2. **(Optionnel) Configurer l'environnement** :
   ```bash
   cp .env.example .env
   # Modifier JWT_SECRET_KEY dans .env pour la production
   ```

3. **Lancer les conteneurs** :
   ```bash
   docker compose up --build
   ```

4. **Accéder à l'application** :
   - 🌐 **Frontend** : [http://localhost:3000](http://localhost:3000)
   - 🔌 **API & Documentation Swagger** : [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option 2 : En Local (Développement)

#### 1. Backend (Python)

Prérequis : Python 3.12+ et le gestionnaire de paquets [`uv`](https://docs.astral.sh/uv/).

```bash
# Installer les dépendances
uv sync

# Initialiser la base de données de mots (si non existante)
uv run python -m src.backend.scripts.seed_db

# Lancer le serveur de développement FastAPI
uv run uvicorn src.backend.main:app --reload --port 8000
```

#### 2. Frontend (React / Vite)

Prérequis : [Node.js 20+](https://nodejs.org/) et npm.

```bash
cd src/frontend

# Installer les dépendances
npm install

# Démarrer le serveur de développement Vite
npm run dev
```

L'interface de développement sera accessible par défaut sur `http://localhost:5173`.

---

## 🧪 Tests & Qualité de Code

### Lancer les tests (Backend)

```bash
uv run pytest
```

### Vérification du style de code (Linter & Type check)

```bash
# Vérification Ruff (linter et formatage)
uv run ruff check .

# Vérification du typage
uv run ty check
```

---

## 📚 Scripts Utilitaires

- **Extraire de nouveaux mots depuis le Wiktionnaire** :
  ```bash
  uv run python -m src.backend.scripts.fetch_wiktionary
  ```
- **Réinitialiser / Alimenter la base de données locale** :
  ```bash
  uv run python -m src.backend.scripts.seed_db
  ```

---

## 🛠️ Stack Technique

- **Backend** : FastAPI, Uvicorn, SQLAlchemy 2.0, SQLite, Pydantic 2, PyJWT, Bcrypt, WebSockets.
- **Frontend** : React 19, Vite 8, Nginx.
- **Outillage & DevOps** : Astral `uv`, Docker, Docker Compose, Pytest, Ruff, Oxlint.

---

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus d'informations.

