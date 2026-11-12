from fastapi import APIRouter, Depends

from app.schemas.ollama import OllamaStatus
from app.services.ollama import OllamaService, get_ollama_service

router = APIRouter(prefix="/api")


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Indique que l'API StudyAI est en mesure de répondre."""
    return {"status": "ok"}


@router.get(
    "/ollama/status",
    response_model=OllamaStatus,
    tags=["ollama"],
)
async def ollama_status(
    service: OllamaService = Depends(get_ollama_service),
) -> OllamaStatus:
    """Vérifie Ollama et la présence du modèle configuré."""
    return await service.get_status()
