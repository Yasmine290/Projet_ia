import json

import httpx
from fastapi import Depends

from app.core.config import Settings, get_settings
from app.schemas.ollama import OllamaStatus


class OllamaService:
    """Centralise les requêtes vers l'API locale d'Ollama."""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.transport = transport

    async def get_status(self) -> OllamaStatus:
        """Vérifie le service local et cherche le modèle configuré."""
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=3.0,
                transport=self.transport,
            ) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            return OllamaStatus(
                is_available=False,
                model_name=self.model_name,
                model_available=None,
                message=(
                    "Ollama est inaccessible. Vérifiez qu'il est démarré et "
                    f"que son adresse est correcte ({self.base_url})."
                ),
            )
        except json.JSONDecodeError:
            return OllamaStatus(
                is_available=False,
                model_name=self.model_name,
                model_available=None,
                message="Ollama a renvoyé une réponse JSON invalide.",
            )

        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            return OllamaStatus(
                is_available=False,
                model_name=self.model_name,
                model_available=None,
                message="La réponse d'Ollama ne contient pas une liste de modèles valide.",
            )

        installed_names = {
            model.get("name")
            for model in models
            if isinstance(model, dict) and isinstance(model.get("name"), str)
        }
        model_available = self.model_name in installed_names
        if model_available:
            message = "Ollama est prêt et le modèle configuré est disponible."
        else:
            message = (
                f"Le modèle '{self.model_name}' n'est pas installé. "
                f"Installez-le avec « ollama pull {self.model_name} »."
            )

        return OllamaStatus(
            is_available=True,
            model_name=self.model_name,
            model_available=model_available,
            message=message,
        )


def get_ollama_service(
    settings: Settings = Depends(get_settings),
) -> OllamaService:
    return OllamaService(
        base_url=settings.normalized_ollama_base_url,
        model_name=settings.ollama_model,
    )
