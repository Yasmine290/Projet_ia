# StudyAI

StudyAI est un assistant local d'apprentissage et de révision. Le projet est
développé progressivement afin de conserver la maquette existante lorsqu'elle
sera fournie et de vérifier chaque module avant de passer au suivant.

## État du projet

Le dossier local ne contenait pas encore de fichiers de projet ni de maquette
lors de l'audit initial. La phase 1 met en place l'API FastAPI et son contrôle
de disponibilité d'Ollama. Le frontend sera intégré lorsque sa maquette sera
disponible.

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
python -m uvicorn app.main:app --app-dir backend --reload
```

## Installation sous macOS

Depuis la racine du dépôt :

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
python -m uvicorn app.main:app --app-dir backend --reload
```

L'API est disponible à l'adresse `http://127.0.0.1:8000`. La documentation
interactive est disponible sur `http://127.0.0.1:8000/docs`.

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
