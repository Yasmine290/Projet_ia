import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.answer import GeneratedAnswer
from app.schemas.document import DocumentSearchResult, DocumentSegment
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


def test_generate_answer_requests_structured_output_and_accepts_known_citations() -> None:
    """Le modèle reçoit seulement les passages retrouvés et cite leur identifiant."""
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "answer": "Une leçon importante est présentée.",
                            "citation_ids": ["S1"],
                        },
                        ensure_ascii=False,
                    )
                }
            },
        )

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(respond),
    )
    source = DocumentSearchResult(
        segment=DocumentSegment(
            id="1:line:1:0",
            document_id=1,
            course_id=2,
            location_type="line",
            location_number=1,
            position=0,
            content="Une leçon importante.",
        ),
        document_name="notes.txt",
        file_format="txt",
        distance=0.1,
    )

    result = asyncio.run(service.generate_answer("Que faut-il retenir ?", [source]))

    assert result == GeneratedAnswer(
        answer="Une leçon importante est présentée. [S1]",
        citation_ids=["S1"],
    )
    assert requests[0]["stream"] is False
    assert requests[0]["format"]["properties"]["citation_ids"]["items"]["enum"] == ["S1"]
    assert json.loads(requests[0]["messages"][1]["content"])["sources"][0]["content"] == (
        "Une leçon importante."
    )


def test_generate_answer_rejects_citations_not_in_retrieved_sources() -> None:
    """Une réponse qui invente une référence est refusée avant d'être renvoyée."""
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"answer": "Réponse non étayée [S2].", "citation_ids": ["S2"]}
                    )
                }
            },
        )

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(respond),
    )
    source = DocumentSearchResult(
        segment=DocumentSegment(
            id="1:line:1:0",
            document_id=1,
            course_id=2,
            location_type="line",
            location_number=1,
            position=0,
            content="Texte source.",
        ),
        document_name="notes.txt",
        file_format="txt",
        distance=0.1,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(service.generate_answer("Question ?", [source]))

    assert error.value.status_code == 502


def test_generate_answer_reports_generation_timeout() -> None:
    """Un délai dépassé est distingué d'une réponse mal formée du modèle."""
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(timeout),
    )
    source = DocumentSearchResult(
        segment=DocumentSegment(
            id="1:line:1:0",
            document_id=1,
            course_id=2,
            location_type="line",
            location_number=1,
            position=0,
            content="Texte source.",
        ),
        document_name="notes.txt",
        file_format="txt",
        distance=0.1,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(service.generate_answer("Question ?", [source]))

    assert error.value.status_code == 504
