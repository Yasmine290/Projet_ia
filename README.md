# StudyAI

StudyAI est un assistant local d'apprentissage et de révision. Le projet est
développé progressivement afin de conserver la maquette existante lorsqu'elle
sera fournie et de vérifier chaque module avant de passer au suivant.

## État du projet

Le dossier local ne contenait pas encore de fichiers de projet ni de maquette
lors de l'audit initial. La phase 1 met en place l'API FastAPI et son contrôle
de disponibilité d'Ollama. Le frontend sera intégré lorsque sa maquette sera
disponible. La phase 2 ajoute SQLite, les cours et l'importation des PDF.

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

## API initiale

- `GET /api/health` : vérifie que l'API répond.
- `GET /api/ollama/status` : vérifie la connexion à Ollama et la présence du
  modèle configuré.
- `POST /api/courses`, `GET /api/courses` : créer et lister les cours.
- `GET`, `PATCH`, `DELETE /api/courses/{course_id}` : consulter, modifier et
  supprimer un cours. Les documents doivent être supprimés avant leur cours.
- `POST`, `GET /api/courses/{course_id}/documents` : importer ou lister les PDF.
- `GET`, `DELETE /api/documents/{document_id}` : consulter ou supprimer un PDF.

Les PDF sont limités à 10 Mio par défaut (`MAX_UPLOAD_BYTES`). Un fichier sans
texte reçoit le statut `ocr_required` ; l'OCR n'est pas pris en charge.
Les autres reçoivent `pending_indexing` : l'indexation, la recherche RAG et les
réponses générées ne sont pas encore implémentées. Ce prototype est local et
ne propose ni comptes ni authentification ; ne l'exposez pas publiquement.
La détection OCR indique seulement l'absence de texte dans tout le document :
elle ne détecte pas les pages scannées au sein d'un document mixte.
En cas d'interruption pendant une suppression, un fichier temporaire se terminant
par `.deleting` peut nécessiter une vérification manuelle dans `backend/data/uploads/`.

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
