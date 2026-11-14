# StudyAI frontend

L'interface utilise JavaScript et JSX avec des feuilles CSS standard : Tailwind
et TypeScript ne sont pas requis. L'architecture garde des dossiers simples :
`pages` pour les écrans, `components` pour les éléments réutilisables, `layouts`
pour la navigation, `context` pour les états partagés, `services` pour les appels
API et `styles` pour les feuilles CSS.

## Lancement local

Prérequis : Node.js 20 à 24 et npm. Depuis la racine du dépôt :

```powershell
cd frontend
npm ci
npm run dev
```

Le frontend est servi sur `http://127.0.0.1:5173`. Vite relaie `/api` vers le
backend FastAPI sur le port 8001. Le backend doit être démarré séparément.

Pour utiliser une autre adresse d'API, copier `.env.example` vers `.env.local`
et modifier `VITE_API_BASE_URL`.

Les comptes, cours, documents et réponses de l'assistant sont connectés à l'API.
Les quiz, résumés, progression et révisions restent indisponibles jusqu'à
l'implémentation de leurs services backend ; aucune donnée fictive n'est affichée.
