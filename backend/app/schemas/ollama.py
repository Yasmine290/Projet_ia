from pydantic import BaseModel


class OllamaStatus(BaseModel):
    """État de la connexion Ollama et du modèle requis par StudyAI."""

    is_available: bool
    model_name: str
    model_available: bool | None
    message: str
