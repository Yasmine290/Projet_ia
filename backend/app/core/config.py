from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Paramètres locaux de l'API, surchargeables par variables d'environnement."""

    app_name: str = "StudyAI API"
    ollama_base_url: HttpUrl = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    database_url: str = "sqlite:///./data/studyai.db"
    chroma_path: Path = Path("data/chroma")
    upload_dir: Path = Path("data/uploads")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    chunk_size: int = Field(default=1000, ge=64, le=5000)
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def normalized_ollama_base_url(self) -> str:
        return str(self.ollama_base_url).rstrip("/")

    @property
    def resolved_upload_dir(self) -> Path:
        """Les chemins relatifs restent identiques quel que soit le répertoire courant."""
        return (BACKEND_DIR / self.upload_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    """Retourne une instance unique de la configuration."""
    return Settings()
