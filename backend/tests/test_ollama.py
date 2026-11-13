import asyncio

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ollama import OllamaStatus
from app.services.ollama import OllamaService, get_ollama_service

client = TestClient(app)


def test_ollama_status_reports_installed_model() -> None:
    """Simule Ollama pour vérifier la détection du modèle sans le télécharger."""
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(respond),
    )

    result = asyncio.run(service.get_status())

    assert result.is_available is True
    assert result.model_available is True


def test_ollama_status_reports_missing_model() -> None:
    """Vérifie que l'API signale le modèle absent et propose son installation."""
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(respond),
    )

    result = asyncio.run(service.get_status())

    assert result.is_available is True
    assert result.model_available is False
    assert "ollama pull qwen3:4b" in result.message


def test_ollama_status_handles_unavailable_service() -> None:
    """Une panne d'Ollama ne doit pas faire échouer le backend."""
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(fail),
    )

    result = asyncio.run(service.get_status())

    assert result.is_available is False
    assert result.model_available is None
    assert "inaccessible" in result.message


def test_ollama_status_endpoint_uses_service_dependency() -> None:
    """Remplace le service réseau pour tester la route indépendamment d'Ollama."""
    async def fake_status() -> OllamaStatus:
        return OllamaStatus(
            is_available=True,
            model_name="qwen3:4b",
            model_available=True,
            message="Ollama est prêt.",
        )

    class FakeOllamaService:
        async def get_status(self) -> OllamaStatus:
            return await fake_status()

    app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    try:
        response = client.get("/api/ollama/status")
    finally:
        app.dependency_overrides.pop(get_ollama_service, None)

    assert response.status_code == 200
    assert response.json()["model_available"] is True
