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
from app.services.ollama import (
    AnswerStreamComplete,
    AnswerStreamDelta,
    OllamaService,
    get_ollama_service,
)

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
    user_message = requests[0]["messages"][1]["content"]
    assert "Question : Que faut-il retenir ?" in user_message
    assert "[S1]" in user_message
    assert "Une leçon importante." in user_message


def test_generate_answer_stream_decodes_json_answer_fragments() -> None:
    """Les fragments JSON et échappements Unicode sont diffusés comme du texte."""
    requests = []
    fragments = [
        '{"answer":"L\\u00',
        'e9tude progresse [S1].","citation_ids":["S1"]}',
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        lines = [
            json.dumps(
                {"message": {"content": fragment}, "done": False},
                ensure_ascii=False,
            )
            for fragment in fragments
        ]
        lines.append(
            json.dumps(
                {"message": {"content": ""}, "done": True},
                ensure_ascii=False,
            )
        )
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode("utf-8"))

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(respond),
    )
    source = DocumentSearchResult(
        segment=DocumentSegment(
            id="1:page:1:0",
            document_id=1,
            course_id=2,
            location_type="page",
            location_number=1,
            position=0,
            content="Le document présente une notion.",
        ),
        document_name="cours.pdf",
        file_format="pdf",
        distance=0.1,
    )

    async def collect_events():
        return [
            event
            async for event in service.generate_answer_stream(
                "Que présente le document ?", [source]
            )
        ]

    events = asyncio.run(collect_events())

    deltas = [event.text for event in events if isinstance(event, AnswerStreamDelta)]
    completed = next(event for event in events if isinstance(event, AnswerStreamComplete))
    assert "".join(deltas) == "Létude progresse [S1]."
    assert completed.generated.answer == "Létude progresse [S1]."
    assert requests[0]["stream"] is True


@pytest.mark.parametrize(
    ("kind", "section_count", "card_count", "prompt_text"),
    [
        ("short", 2, 0, "Crée un résumé court"),
        ("detailed", 3, 0, "Crée un résumé détaillé"),
        ("sheet", 2, 3, "Crée une fiche de révision"),
    ],
)
def test_generate_study_guide_returns_validated_content(
    kind, section_count, card_count, prompt_text
) -> None:
    """Les trois formats respectent leur structure et citent les sources reçues."""
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
                            "title": "Les bases de la photosynthèse",
                            "intro": "La photosynthèse convertit l'énergie lumineuse.",
                            "sections": [
                                {
                                    "title": f"Notion {index}",
                                    "text": "La photosynthèse produit du glucose.",
                                }
                                for index in range(section_count)
                            ],
                            "flashcards": [
                                {
                                    "question": f"Question {index} ?",
                                    "answer": "Réponse fondée sur la source.",
                                }
                                for index in range(card_count)
                            ],
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
            id="1:page:2:0",
            document_id=1,
            course_id=2,
            location_type="page",
            location_number=2,
            position=0,
            content="La photosynthèse produit du glucose et libère de l'oxygène.",
        ),
        document_name="biologie.pdf",
        file_format="pdf",
        distance=0.1,
    )

    result = asyncio.run(service.generate_study_guide(kind, [source]))

    assert result.title == "Les bases de la photosynthèse"
    assert len(result.sections) == section_count
    assert len(result.flashcards) == card_count
    assert result.citation_ids == ["S1"]
    assert requests[0]["stream"] is False
    assert requests[0]["format"]["properties"]["flashcards"]["maxItems"] == (
        5 if kind == "sheet" else 0
    )
    assert prompt_text in requests[0]["messages"][1]["content"]


def test_generate_study_guide_rejects_unknown_citation_ids() -> None:
    """Une référence absente des passages reçus ne doit pas être acceptée."""
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "title": "Résumé",
                            "intro": "Introduction.",
                            "sections": [],
                            "flashcards": [],
                            "citation_ids": ["S2"],
                        }
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

    with pytest.raises(HTTPException, match="références de source invalides"):
        asyncio.run(service.generate_study_guide("short", [source]))


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


def test_generate_answer_rejects_response_that_only_repeats_question() -> None:
    """Une question répétée avec des citations ne doit pas passer pour une réponse."""
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "answer": "Le chapitre parle de quoi ? [S1]",
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
            id="1:page:1:0",
            document_id=1,
            course_id=2,
            location_type="page",
            location_number=1,
            position=0,
            content="Le cours aborde plusieurs notions.",
        ),
        document_name="cours.pdf",
        file_format="pdf",
        distance=0.1,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(service.generate_answer("Le chapitre parle de quoi ?", [source]))

    assert error.value.status_code == 502
    assert "répété la question" in error.value.detail


def test_generate_answer_reports_generation_timeout() -> None:
    """Un délai dépassé est distingué d'une réponse mal formée du modèle."""
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    service = OllamaService(
        base_url="http://ollama.test",
        model_name="qwen3:4b",
        transport=httpx.MockTransport(timeout),
    )
    assert service.generation_timeout_seconds == 600
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
