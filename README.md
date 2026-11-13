# StudyAI

StudyAI est un assistant local d'apprentissage et de révision. Le projet est
développé progressivement afin de conserver la maquette existante lorsqu'elle
sera fournie et de vérifier chaque module avant de passer au suivant.

## État du projet

Le dossier local ne contenait pas encore de fichiers de projet ni de maquette
lors de l'audit initial. La phase 1 met en place l'API FastAPI et son contrôle
de disponibilité d'Ollama. Le frontend sera intégré lorsque sa maquette sera
disponible. La phase 2 ajoute SQLite, les cours et l'importation des PDF.
Des comptes locaux protègent désormais les cours et documents par utilisateur.

## Prérequis

- Python 3.11 ou supérieur.
- Ollama installé localement pour tester l'intégration au modèle.
- Le modèle `qwen3:4b` (facultatif pour démarrer l'API).

L'API démarre même si Ollama ou le modèle configuré n'est pas disponible.

## Installation sous Windows (PowerShell)

Depuis la racine du dépôt :

```powershell
py -3 -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
python -m alembic -c backend\alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir backend --reload --port 8001
```

## Installation sous macOS

Depuis la racine du dépôt :

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir backend --reload --port 8001
```

L'API est disponible à l'adresse `http://127.0.0.1:8001`. La documentation
interactive est disponible sur `http://127.0.0.1:8001/docs`.

La commande Alembic initialise et met à jour le schéma SQLite ; exécutez-la
après une mise à jour contenant de nouvelles migrations. Par défaut, la base
et les fichiers sont enregistrés dans `backend/data/`, qui n'est pas versionné.
Les chemins relatifs de la configuration sont résolus depuis `backend/`.

## Configuration d'Ollama

Si Ollama est installé, démarrez-le puis téléchargez le modèle configuré :

```text
ollama pull qwen3:4b
```

La configuration locale se trouve dans `backend/.env`. Les valeurs par défaut
fonctionnent avec Ollama à `http://localhost:11434` et le modèle `qwen3:4b`.
Ne commitez pas le fichier `.env`.

## Comptes locaux et API

La connexion utilise des comptes locaux, des mots de passe hachés avec Argon2
et des jetons de session aléatoires valables 12 heures. Chaque compte ne peut
accéder qu'à ses propres cours et documents.

Depuis `http://127.0.0.1:8001/docs` :

1. Utiliser `POST /api/auth/register` avec un nom d'utilisateur de 3 à 50
   caractères (`a-z`, chiffres, `_`, `-`, `.`) et un mot de passe de 12 à 128
   caractères.
2. Utiliser `POST /api/auth/login` avec les mêmes identifiants.
3. Copier le `access_token` retourné dans **Authorize** pour appeler les routes
   protégées. Ne partagez pas ce jeton.
4. Utiliser `POST /api/auth/logout` pour révoquer la session.

`GET /api/auth/me` affiche le compte associé au jeton. L'interface React et les
fonctions de changement ou récupération du mot de passe ne sont pas encore
implémentées.

### Anciens cours sans compte

La migration conserve les cours créés avant l'authentification mais ne les
attribue pas automatiquement : ils restent invisibles jusqu'à une attribution
manuelle. Après avoir sauvegardé la base locale, créé le compte voulu et vérifié
son nom, exécuter depuis le dossier `backend` avec l'environnement virtuel actif :

```text
python -m app.claim_courses nom_du_compte --confirm
```

Cette opération attribue **tous** les anciens cours sans propriétaire, ainsi que
leurs documents, au compte indiqué ; elle ne modifie pas les cours déjà attribués.
Ne l'exécutez que si ce transfert est souhaité.

### Routes

- `GET /api/health` : vérifie que l'API répond.
- `GET /api/ollama/status` : vérifie la connexion à Ollama et la présence du
  modèle configuré.
- `POST /api/courses`, `GET /api/courses` : créer et lister les cours.
- `GET`, `PATCH`, `DELETE /api/courses/{course_id}` : consulter, modifier et
  supprimer un cours. Les documents doivent être supprimés avant leur cours.
- `POST`, `GET /api/courses/{course_id}/documents` : importer ou lister les PDF.
- `GET`, `DELETE /api/documents/{document_id}` : consulter ou supprimer un PDF.
- `GET /api/documents/{document_id}/segments` : extraire le texte page par page
  et le découper en passages avec leurs références. Ce calcul ne stocke ni
  n'indexe les passages ; il est effectué à chaque appel.

Les PDF sont limités à 10 Mio par défaut (`MAX_UPLOAD_BYTES`). Un fichier sans
texte reçoit le statut `ocr_required` ; l'OCR n'est pas pris en charge.
Les autres reçoivent `pending_indexing` : l'indexation, la recherche RAG et les
réponses générées ne sont pas encore implémentées. Ce prototype reste local :
ne l'exposez pas publiquement. Il n'y a pas encore de limitation des tentatives
de connexion, de récupération des comptes ni de configuration HTTPS. Les
comptes applicatifs ne protègent pas les fichiers SQLite et PDF contre une
personne ayant accès au système de fichiers de l'ordinateur.
La détection OCR indique seulement l'absence de texte dans tout le document :
elle ne détecte pas les pages scannées au sein d'un document mixte.
En cas d'interruption pendant une suppression, un fichier temporaire se terminant
par `.deleting` peut nécessiter une vérification manuelle dans `backend/data/uploads/`.

Le découpage limite chaque passage à `CHUNK_SIZE` caractères (1000 par défaut,
entre 64 et 5000). Il privilégie les fins de phrase puis les espaces, et conserve
le numéro de page. Les blancs sont normalisés ; le contenu et l'ordre exacts
peuvent dépendre de l'extraction de PyMuPDF et de la mise en page du PDF.

## Tests

Depuis la racine du dépôt, avec l'environnement virtuel activé :

```powershell
python -m pytest backend\tests
```

La même commande fonctionne sous macOS en remplaçant les séparateurs par `/` :

```bash
python -m pytest backend/tests
```

Les tests de la phase 1 simulent Ollama et ne nécessitent pas de modèle
téléchargé.

## Références techniques

- [FastAPI — premiers pas](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Ollama API — liste des modèles](https://docs.ollama.com/api/tags)
- [SQLAlchemy — SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [Alembic — migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [FastAPI — fichiers](https://fastapi.tiangolo.com/tutorial/request-files/)
- [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/the-basics.html)
- [FastAPI — mots de passe et sécurité](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [pwdlib — hachage Argon2](https://frankie567.github.io/pwdlib/guide/)
