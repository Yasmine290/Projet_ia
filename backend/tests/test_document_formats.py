from io import BytesIO
import asyncio
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document as WordDocument
from pptx import Presentation
from pptx.util import Inches
import pytest
from fastapi import HTTPException

from test_data import api
from app.services import documents as document_service


def make_docx() -> bytes:
    """Crée un Word de test avec un paragraphe et une table."""
    document = WordDocument()
    document.add_paragraph("Introduction du cours.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Terme"
    table.cell(0, 1).text = "Définition"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def make_pptx() -> bytes:
    """Crée une présentation de test dont le texte est associé à sa diapositive."""
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    textbox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    textbox.text_frame.text = "Objectif du cours."
    output = BytesIO()
    presentation.save(output)
    return output.getvalue()


def test_txt_upload_extraction_and_line_references(api) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Français"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.txt", b"Premiere ligne.\r\n\nDeuxieme ligne.", "text/plain")},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["file_format"] == "txt"
    assert document["unit_type"] == "line"
    assert document["unit_count"] == 3
    segments = client.get(f"/api/documents/{document['id']}/segments").json()
    assert [(item["location_type"], item["location_number"]) for item in segments] == [
        ("line", 1),
        ("line", 3),
    ]


def test_docx_upload_extracts_paragraphs_and_tables(api) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Word"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={
            "file": (
                "cours.docx",
                make_docx(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["file_format"] == "docx"
    assert document["unit_type"] == "paragraph"
    segments = client.get(f"/api/documents/{document['id']}/segments").json()
    assert [segment["content"] for segment in segments] == [
        "Introduction du cours.",
        "Terme | Définition",
    ]
    assert [segment["location_number"] for segment in segments] == [1, 2]


def test_pptx_upload_extracts_slide_references(api) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "PowerPoint"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={
            "file": (
                "cours.pptx",
                make_pptx(),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["file_format"] == "pptx"
    assert document["unit_type"] == "slide"
    segments = client.get(f"/api/documents/{document['id']}/segments").json()
    assert len(segments) == 1
    assert segments[0]["location_type"] == "slide"
    assert segments[0]["location_number"] == 1
    assert segments[0]["content"] == "Objectif du cours."


def test_rejects_spoofed_archives_legacy_without_converter_and_non_utf8_text(
    api, monkeypatch
) -> None:
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Sécurité"}).json()["id"]
    endpoint = f"/api/courses/{course_id}/documents"
    monkeypatch.setattr(document_service, "_find_libreoffice", lambda configured: None)
    bad_archive = BytesIO()
    with ZipFile(bad_archive, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("evil.txt", "pas un document Word")

    cases = [
        ("fake.docx", bad_archive.getvalue(), 415),
        ("ancien.doc", b"ancien Word", 503),
        ("ancien.ppt", b"ancien PowerPoint", 503),
        ("texte.txt", b"\xff\xfe", 415),
        ("notes.exe", b"contenu", 415),
    ]
    for filename, content, expected_status in cases:
        response = client.post(
            endpoint,
            files={"file": (filename, content, "application/octet-stream")},
        )
        assert response.status_code == expected_status, (filename, response.text)
    assert list((tmp_path / "uploads").iterdir()) == []


def test_empty_text_document_has_explicit_status(api) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Vide"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("vide.txt", b" \n\t", "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "no_text"
    assert client.get(f"/api/documents/{response.json()['id']}/segments").status_code == 422


def test_rejects_archive_with_excessive_expanded_size(tmp_path) -> None:
    """Un petit fichier ZIP ne peut pas décompresser au-delà de la limite définie."""
    from fastapi import HTTPException
    import pytest

    from app.services.documents import extract_text_units

    archive_path = tmp_path / "trop_volumineux.docx"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "x" * 100)
        archive.writestr("word/document.xml", "y" * 100)

    with pytest.raises(HTTPException) as error:
        extract_text_units(archive_path, "docx", max_archive_entries=10, max_expanded_bytes=50)
    assert error.value.status_code == 413


def test_malformed_office_xml_returns_client_error_not_server_error(api) -> None:
    """Un ZIP ayant les bons noms mais un XML endommagé est rejeté clairement."""
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Sécurité"}).json()["id"]
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<document><body>")
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("malforme.docx", archive.getvalue(), "application/octet-stream")},
    )
    assert response.status_code == 422, response.text
    assert list((tmp_path / "uploads").iterdir()) == []


@pytest.mark.parametrize(
    ("legacy_name", "converted_extension", "create_content", "expected_location"),
    [
        ("ancien.doc", ".docx", make_docx, "paragraph"),
        ("ancien.ppt", ".pptx", make_pptx, "slide"),
    ],
)
def test_legacy_office_upload_uses_configured_converter(
    api, monkeypatch, legacy_name, converted_extension, create_content, expected_location
) -> None:
    """DOC/PPT passent par le convertisseur puis l'extraction Office standard."""
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Ancien cours"}).json()["id"]
    monkeypatch.setattr(document_service, "_find_libreoffice", lambda configured: "soffice-test")

    async def fake_conversion(executable, source_path, output_path, timeout_seconds):
        assert executable == "soffice-test"
        assert source_path.suffix == f".{legacy_name.rsplit('.', 1)[1]}"
        assert output_path.suffix == converted_extension
        assert timeout_seconds == 60
        output_path.write_bytes(create_content())

    monkeypatch.setattr(document_service, "_convert_legacy_office", fake_conversion)
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": (legacy_name, b"legacy office content", "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    metadata = response.json()
    assert metadata["file_format"] == legacy_name.rsplit(".", 1)[1]
    assert metadata["original_name"] == legacy_name
    assert metadata["unit_type"] == expected_location
    assert len(list((tmp_path / "uploads").iterdir())) == 1
    stored_path = next((tmp_path / "uploads").iterdir())
    assert stored_path.suffix == converted_extension
    segments = client.get(f"/api/documents/{metadata['id']}/segments").json()
    assert segments[0]["location_type"] == expected_location


def test_legacy_office_upload_explains_missing_libreoffice(api, monkeypatch) -> None:
    """Sans LibreOffice, les anciens formats échouent sans laisser de fichier."""
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Ancien cours"}).json()["id"]
    monkeypatch.setattr(document_service, "_find_libreoffice", lambda configured: None)
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("ancien.doc", b"legacy content", "application/msword")},
    )
    assert response.status_code == 503
    assert "LibreOffice" in response.json()["detail"]
    assert not (tmp_path / "uploads").exists()


def test_legacy_converter_uses_timeout_and_argument_list(tmp_path, monkeypatch) -> None:
    """Le convertisseur ne passe pas par un shell et interrompt les traitements bloqués."""
    source = tmp_path / "un document.doc"
    output = tmp_path / "un document.docx"
    source.write_bytes(b"contenu")
    calls = []

    class HungProcess:
        returncode = None

        async def wait(self):
            if self.returncode is None:
                await asyncio.sleep(10)

        def kill(self):
            self.returncode = -9

    async def start(*args, **kwargs):
        calls.append((args, kwargs))
        return HungProcess()

    monkeypatch.setattr(document_service.asyncio, "create_subprocess_exec", start)
    with pytest.raises(HTTPException) as error:
        asyncio.run(document_service._convert_legacy_office("soffice-test", source, output, 1))
    assert error.value.status_code == 422
    command, options = calls[0]
    assert command[0] == "soffice-test"
    assert command[-1] == str(source)
    assert "--convert-to" in command
    assert options["stdout"] == document_service.subprocess.DEVNULL
    assert options["stderr"] == document_service.subprocess.DEVNULL
