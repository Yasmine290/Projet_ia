from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document as WordDocument
from pptx import Presentation
from pptx.util import Inches

from test_data import api


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


def test_rejects_spoofed_archives_legacy_formats_and_non_utf8_text(api) -> None:
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Sécurité"}).json()["id"]
    endpoint = f"/api/courses/{course_id}/documents"
    bad_archive = BytesIO()
    with ZipFile(bad_archive, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("evil.txt", "pas un document Word")

    cases = [
        ("fake.docx", bad_archive.getvalue(), 415),
        ("ancien.doc", b"ancien Word", 415),
        ("ancien.ppt", b"ancien PowerPoint", 415),
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
