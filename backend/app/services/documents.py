from io import BytesIO
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pymupdf
from docx import Document as WordDocument
from docx.opc.exceptions import PackageNotFoundError as WordPackageNotFoundError
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from fastapi import HTTPException, UploadFile
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.exc import PackageNotFoundError as PowerPointPackageNotFoundError
from lxml.etree import LxmlError

from app.schemas.document import DocumentSegment

SUPPORTED_FORMATS = {"pdf", "docx", "pptx", "txt"}
LEGACY_FORMATS = {"doc", "ppt"}
PDF_MIME_HEADER = b"%PDF-"
OFFICE_REQUIRED_MEMBERS = {
    "docx": {"[Content_Types].xml", "word/document.xml"},
    "pptx": {"[Content_Types].xml", "ppt/presentation.xml"},
}


@dataclass(frozen=True)
class TextUnit:
    """Unité textuelle repérable dans le format d'origine."""

    location_type: Literal["page", "slide", "paragraph", "line"]
    location_number: int
    content: str


def resolve_document_path(upload_dir: Path, storage_name: str) -> Path:
    """Refuse les noms et liens susceptibles de sortir du dossier d'importation."""
    if Path(storage_name).name != storage_name or storage_name in {".", ".."}:
        raise HTTPException(status_code=500, detail="Chemin de document invalide.")
    path = upload_dir / storage_name
    if path.is_symlink():
        raise HTTPException(status_code=500, detail="Lien de document non autorisé.")
    return path


def split_text(text: str, chunk_size: int) -> list[str]:
    """Découpe un texte nettoyé en passages de taille maximale, sans perdre de mots."""
    if chunk_size < 1:
        raise ValueError("La taille des segments doit être positive.")
    text = re.sub(r"\s+", " ", text).strip()
    chunks: list[str] = []
    while len(text) > chunk_size:
        window = text[:chunk_size]
        # Préférer une fin de phrase ; sinon couper à un espace, ou dans un mot
        # uniquement si celui-ci dépasse à lui seul la taille maximale.
        endings = list(re.finditer(r"[.!?](?=\s|$)", window))
        boundary = endings[-1].end() if endings else window.rfind(" ")
        if boundary <= 0:
            boundary = chunk_size
        chunks.append(text[:boundary].strip())
        text = text[boundary:].strip()
    if text:
        chunks.append(text)
    return chunks


def _validate_office_archive(
    path: Path, file_format: str, max_entries: int, max_expanded_bytes: int
) -> None:
    """Vérifie la structure et la taille décompressée sans extraire l'archive."""
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > max_entries:
                raise HTTPException(status_code=413, detail="L'archive contient trop d'éléments.")
            if sum(member.file_size for member in members) > max_expanded_bytes:
                raise HTTPException(status_code=413, detail="Le contenu décompressé est trop volumineux.")
            names = {member.filename for member in members}
            if not OFFICE_REQUIRED_MEMBERS[file_format].issubset(names):
                raise HTTPException(status_code=415, detail="Le fichier Office ne possède pas une structure valide.")
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=415, detail="Le fichier Office n'est pas une archive valide.") from exc


def _extract_docx(path: Path) -> list[TextUnit]:
    """Lit les paragraphes et tableaux dans leur ordre d'apparition dans Word."""
    # Fournir les octets au parseur évite de laisser un handle sur disque ouvert.
    document = WordDocument(BytesIO(path.read_bytes()))
    units: list[TextUnit] = []
    block_number = 0
    for element in document.element.body.iterchildren():
        if isinstance(element, CT_P):
            text = Paragraph(element, document).text
        elif isinstance(element, CT_Tbl):
            table = Table(element, document)
            # Les lignes de tableau sont aplaties en texte en conservant leur ordre.
            text = "\n".join(
                " | ".join(cell.text for cell in row.cells)
                for row in table.rows
            )
        else:
            continue
        block_number += 1
        units.append(TextUnit("paragraph", block_number, text))
    return units


def _extract_pptx(path: Path) -> list[TextUnit]:
    """Récupère le texte des formes et tableaux, diapositive par diapositive."""
    presentation = Presentation(BytesIO(path.read_bytes()))
    units: list[TextUnit] = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        slide_text: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.strip():
                slide_text.append(shape.text)
            if shape.has_table:
                slide_text.extend(
                    " | ".join(cell.text for cell in row.cells)
                    for row in shape.table.rows
                )
            # Le texte des groupes de formes n'est pas ignoré silencieusement.
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                for grouped_shape in shape.shapes:
                    if grouped_shape.has_text_frame and grouped_shape.text.strip():
                        slide_text.append(grouped_shape.text)
        # Conserver aussi les diapositives vides afin que le total soit exact.
        units.append(TextUnit("slide", slide_number, "\n".join(slide_text)))
    return units


def extract_text_units(
    path: Path,
    file_format: str,
    max_archive_entries: int,
    max_expanded_bytes: int,
) -> list[TextUnit]:
    """Extrait le texte en conservant le type et le numéro de chaque repère."""
    if not path.is_file():
        raise HTTPException(status_code=422, detail="Le fichier du document est inaccessible.")
    try:
        if file_format == "pdf":
            with pymupdf.open(path) as pdf:
                if not pdf.is_pdf or pdf.needs_pass:
                    raise HTTPException(status_code=422, detail="PDF protégé ou invalide.")
                return [
                    TextUnit("page", page_number, page.get_text())
                    for page_number, page in enumerate(pdf, start=1)
                ]
        if file_format == "txt":
            text = path.read_text(encoding="utf-8-sig")
            return [
                TextUnit("line", line_number, line)
                for line_number, line in enumerate(text.splitlines(), start=1)
            ]
        if file_format in OFFICE_REQUIRED_MEMBERS:
            _validate_office_archive(path, file_format, max_archive_entries, max_expanded_bytes)
            if file_format == "docx":
                return _extract_docx(path)
            return _extract_pptx(path)
    except HTTPException:
        raise
    except (
        pymupdf.FileDataError,
        pymupdf.EmptyFileError,
        UnicodeDecodeError,
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        zipfile.BadZipFile,
        WordPackageNotFoundError,
        PowerPointPackageNotFoundError,
        LxmlError,
        AttributeError,
    ) as exc:
        raise HTTPException(
            status_code=422, detail=f"Le fichier {file_format.upper()} est illisible ou endommagé."
        ) from exc
    raise HTTPException(status_code=415, detail="Format de document non pris en charge.")


def extract_segments(
    path: Path,
    file_format: str,
    document_id: int,
    course_id: int,
    chunk_size: int,
    max_archive_entries: int,
    max_expanded_bytes: int,
) -> list[DocumentSegment]:
    """Transforme les unités extraites en passages avec des références de source."""
    units = extract_text_units(path, file_format, max_archive_entries, max_expanded_bytes)
    segments: list[DocumentSegment] = []
    for unit in units:
        for position, content in enumerate(split_text(unit.content, chunk_size)):
            segments.append(
                DocumentSegment(
                    id=f"{document_id}:{unit.location_type}:{unit.location_number}:{position}",
                    document_id=document_id,
                    course_id=course_id,
                    location_type=unit.location_type,
                    location_number=unit.location_number,
                    position=position,
                    content=content,
                )
            )
    if not segments:
        if file_format == "pdf":
            raise HTTPException(status_code=422, detail="Aucun texte détecté ; l'OCR n'est pas pris en charge.")
        raise HTTPException(status_code=422, detail="Aucun texte exploitable n'a été détecté dans le document.")
    return segments


async def store_document(
    file: UploadFile,
    upload_dir: Path,
    max_bytes: int,
    max_archive_entries: int,
    max_expanded_bytes: int,
) -> tuple[str, str, str, int | None, str]:
    """Valide et stocke un document sous un nom généré par l'application."""
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if suffix in LEGACY_FORMATS:
        raise HTTPException(
            status_code=415,
            detail=f"Le format .{suffix} nécessite une conversion LibreOffice, pas encore activée.",
        )
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=415, detail="Formats acceptés : PDF, DOCX, PPTX et TXT.")

    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid4().hex}.{suffix}"
    path = upload_dir / storage_name
    size = 0
    valid = False
    created = False
    try:
        # La lecture par blocs applique une limite même si le client ment sur la taille.
        with path.open("xb") as destination:
            created = True
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="Le document dépasse la taille autorisée.")
                destination.write(chunk)

        if suffix == "pdf":
            with path.open("rb") as source:
                if source.read(len(PDF_MIME_HEADER)) != PDF_MIME_HEADER:
                    raise HTTPException(status_code=415, detail="Le fichier n'est pas un PDF valide.")
        elif suffix in OFFICE_REQUIRED_MEMBERS:
            _validate_office_archive(path, suffix, max_archive_entries, max_expanded_bytes)
        else:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=415, detail="Le fichier TXT doit être encodé en UTF-8.") from exc
            if "\x00" in text:
                raise HTTPException(status_code=415, detail="Le fichier TXT contient des octets nuls.")

        units = extract_text_units(path, suffix, max_archive_entries, max_expanded_bytes)
        unit_type = {"pdf": "page", "docx": "paragraph", "pptx": "slide", "txt": "line"}[suffix]
        unit_count = len(units)
        has_text = any(unit.content.strip() for unit in units)
        if suffix == "pdf" and not has_text:
            processing_status = "ocr_required"
        else:
            processing_status = "pending_indexing" if has_text else "no_text"
        valid = True
        return storage_name, suffix, unit_type, unit_count, processing_status
    finally:
        if created and not valid:
            path.unlink(missing_ok=True)
        await file.close()
