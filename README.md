# StudyAI

StudyAI est un assistant local d'apprentissage et de révision. Le projet est
développé progressivement autour d'une interface React en JavaScript/JSX avec
du CSS standard, et d'une API FastAPI.
La maquette fournie sert de référence visuelle ; les écrans connectés affichent
les données réelles de l'API plutôt que les contenus fictifs de la démonstration.

## État du projet

Le backend FastAPI gère l'authentification, les cours, les documents multi-formats,
l'indexation vectorielle et les réponses RAG avec citations. Le frontend React
intègre les parcours de connexion, cours, documents et assistant. Les quiz,
résumés, progression et révisions restent indisponibles jusqu'à l'ajout de leurs
services backend.

## Prérequis

- Python 3.11 ou supérieur.
- Ollama installé localement pour tester l'intégration au modèle.
- Le modèle `qwen3:4b` (facultatif pour démarrer l'API).
- Node.js 20 à 24 et npm (facultatifs, pour démarrer le frontend).

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

## Lancer le frontend

Démarrez d'abord l'API sur le port 8001, puis, dans un autre terminal depuis la
racine du dépôt :

```powershell
cd frontend
npm ci
npm run dev
```

Le frontend est disponible sur `http://127.0.0.1:5173`. Vite relaie les appels
`/api` vers le backend local sur `http://127.0.0.1:8001`. Le fichier
`frontend/.env.example` documente la configuration d'une autre adresse API.
Les dépendances npm et les fichiers `.env.local` ne contiennent aucun secret du
backend et le fichier `.env.local` ne doit pas être commité.

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

`GET /api/auth/me` affiche le compte associé au jeton. L'interface React montre
le nom du compte et permet de révoquer sa session ; le changement et la
récupération du mot de passe ne sont pas encore implémentés.

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
- `POST`, `GET /api/courses/{course_id}/documents` : importer ou lister les documents.
- `GET`, `DELETE /api/documents/{document_id}` : consulter ou supprimer un document.
- `GET /api/documents/{document_id}/segments` : extraire le texte et le découper
  en passages avec leurs références.
- `POST /api/documents/{document_id}/index` : indexer explicitement un document.
- `POST /api/courses/{course_id}/search` : rechercher des passages dans un cours
  (`{"query": "…", "limit": 5}` ; limite de 20 résultats).
- `POST /api/courses/{course_id}/ask` : poser une question à partir des passages
  indexés et recevoir une réponse avec ses citations (`limit` de 1 à 5).

Exemple de corps pour `/ask` : `{"query": "Que faut-il retenir ?", "limit": 5}`.
La génération transmet à l'instance Ollama configurée uniquement la question et
les passages retrouvés ; les identifiants de citation sont vérifiés et leurs
marqueurs sont ajoutés ou validés avant le retour. Si aucun passage n'est
retrouvé, l'API le signale sans appeler le modèle. Le délai maximal est configurable avec
`OLLAMA_GENERATION_TIMEOUT_SECONDS` (120 secondes par défaut).

Formats actuellement acceptés : PDF, DOCX, PPTX, TXT, DOC et PPT. DOC/PPT sont
convertis localement par LibreOffice en DOCX/PPTX lors de l'import ; le fichier
converti est stocké, tandis que le nom et le format d'origine sont conservés dans
les métadonnées. Si LibreOffice est absent, l'import DOC/PPT renvoie une erreur
claire et les autres formats continuent de fonctionner.

Installer LibreOffice sur chaque ordinateur qui doit importer DOC/PPT :

- Windows/macOS : [télécharger LibreOffice](https://www.libreoffice.org/download/download/).
- Si `soffice` n'est pas détecté automatiquement, définir `LIBREOFFICE_PATH`
  dans `backend/.env` avec le chemin vers l'exécutable `soffice`.

La conversion s'exécute sans shell, avec un profil temporaire isolé et un délai
maximum de 60 secondes (`LEGACY_CONVERSION_TIMEOUT_SECONDS`). Elle traite un
document local non fiable ; gardez le prototype hors d'Internet, maintenez
LibreOffice à jour, et n'importez que des fichiers de confiance.

La taille d'import est
limitée à 10 Mio par défaut (`MAX_UPLOAD_BYTES`). Les archives Office sont aussi
limitées à 5000 entrées et 100 Mio décompressés (`MAX_ARCHIVE_ENTRIES`,
`MAX_EXPANDED_BYTES`) pour réduire le risque d'archive malveillante.
Les repères d'extraction sont les pages PDF, toutes les diapositives PPTX, les
blocs (paragraphes et tableaux) DOCX, et les lignes TXT. `unit_count` donne le
nombre de repères du format ; les unités vides ne génèrent pas de passage texte.
Les pages visuelles DOCX ne sont pas calculées. Les anciens formats DOC et PPT
passent par LibreOffice à l'import et gardent leurs références de paragraphe ou
de diapositive après conversion.

Un PDF sans texte reçoit le statut `ocr_required` ; l'OCR n'est pas pris en
charge. Un document vide reçoit `no_text`. Les autres reçoivent
`pending_indexing` jusqu'à l'appel explicite à la route d'indexation. Les vecteurs
sont conservés localement dans `backend/data/chroma/`, et les passages gardent
leurs repères de page, ligne, paragraphe ou diapositive. L'index et chaque
recherche sont filtrés par compte et par cours ; la suppression d'un document
supprime aussi ses vecteurs. Si Chroma ne peut pas les supprimer, l'API conserve
le document en attente d'indexation plutôt que de laisser un index visible.

Sentence Transformers utilise par défaut le modèle
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Ses poids
représentent environ 471 Mo et sont téléchargés depuis Hugging Face au premier
appel d'indexation ou de recherche sur un cours indexé ; le modèle est ensuite
conservé dans le cache local de Hugging Face. L'API ne télécharge ni ne charge
le modèle au démarrage. Ce prototype reste local :
ne l'exposez pas publiquement. Il n'y a pas encore de limitation des tentatives
de connexion, de récupération des comptes ni de configuration HTTPS. Les
comptes applicatifs ne protègent pas les fichiers SQLite et PDF contre une
personne ayant accès au système de fichiers de l'ordinateur.
La détection OCR indique seulement l'absence de texte dans tout le PDF : elle ne
détecte pas les pages scannées au sein d'un PDF mixte.
En cas d'interruption pendant une suppression, un fichier temporaire se terminant
par `.deleting` peut nécessiter une vérification manuelle dans `backend/data/uploads/`.

Le découpage limite chaque passage à `CHUNK_SIZE` caractères (1000 par défaut,
entre 64 et 5000). Il privilégie les fins de phrase puis les espaces, et conserve
le repère propre au format. Les blancs sont normalisés ; la mise en page visuelle
des fichiers bureautiques n'est pas préservée.

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
- [python-docx](https://python-docx.readthedocs.io/en/latest/)
- [python-pptx](https://python-pptx.readthedocs.io/en/latest/)
- [Sentence Transformers](https://www.sbert.net/)
- [ChromaDB — client persistant](https://docs.trychroma.com/docs/run-chroma/clients)
- [Modèle multilingue d'embeddings utilisé](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
