from io import BytesIO
import asyncio
import re
import shutil
import subprocess
import tempfile
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
CONVERTED_FORMATS = {"doc": "docx", "ppt": "pptx"}
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


def _find_libreoffice(configured_path: str | None) -> str | None:
    """Utilise le chemin configuré ou cherche LibreOffice dans le PATH du système."""
    if configured_path:
        configured = shutil.which(configured_path)
        if configured:
            return configured
        if Path(configured_path).is_file():
            return str(Path(configured_path).resolve())
        return None
    return shutil.which("soffice") or shutil.which("libreoffice")


async def _convert_legacy_office(
    executable: str, source_path: Path, output_path: Path, timeout_seconds: int
) -> None:
    """Convertit un ancien document dans un profil LibreOffice temporaire isolé."""
    profile_path = output_path.parent / f"profile-{uuid4().hex}"
    profile_path.mkdir()
    command = [
        executable,
        "--headless",
        "--nologo",
        "--nodefault",
        "--nolockcheck",
        f"-env:UserInstallation={profile_path.as_uri()}",
        "--convert-to",
        output_path.suffix.lstrip("."),
        "--outdir",
        str(output_path.parent),
        str(source_path),
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise HTTPException(
            status_code=503, detail="Impossible de démarrer LibreOffice pour convertir ce fichier."
        ) from exc
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise HTTPException(
            status_code=422, detail="La conversion du document a dépassé le délai autorisé."
        ) from exc
    except asyncio.CancelledError:
        # Un client qui se déconnecte ne doit pas laisser une conversion tourner en arrière-plan.
        process.kill()
        await process.wait()
        raise
    if process.returncode != 0 or not output_path.is_file():
        raise HTTPException(
            status_code=422, detail="LibreOffice n'a pas pu convertir ce document."
        )


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
    extraction_format = CONVERTED_FORMATS.get(file_format, file_format)
    try:
        if extraction_format == "pdf":
            with pymupdf.open(path) as pdf:
                if not pdf.is_pdf or pdf.needs_pass:
                    raise HTTPException(status_code=422, detail="PDF protégé ou invalide.")
                return [
                    TextUnit("page", page_number, page.get_text())
                    for page_number, page in enumerate(pdf, start=1)
                ]
        if extraction_format == "txt":
            text = path.read_text(encoding="utf-8-sig")
            return [
                TextUnit("line", line_number, line)
                for line_number, line in enumerate(text.splitlines(), start=1)
            ]
        if extraction_format in OFFICE_REQUIRED_MEMBERS:
            _validate_office_archive(path, extraction_format, max_archive_entries, max_expanded_bytes)
            if extraction_format == "docx":
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
    libreoffice_path: str | None,
    conversion_timeout_seconds: int,
) -> tuple[str, str, str, int | None, str]:
    """Valide et stocke un document sous un nom généré par l'application."""
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_FORMATS:
        if suffix not in LEGACY_FORMATS:
            await file.close()
            raise HTTPException(status_code=415, detail="Formats acceptés : PDF, DOCX, PPTX, TXT, DOC et PPT.")

    executable = _find_libreoffice(libreoffice_path) if suffix in LEGACY_FORMATS else None
    if suffix in LEGACY_FORMATS and executable is None:
        await file.close()
        raise HTTPException(
            status_code=503,
            detail=(
                f"LibreOffice est nécessaire pour convertir les fichiers .{suffix}. "
                "Installez-le ou configurez LIBREOFFICE_PATH."
            ),
        )

    upload_dir.mkdir(parents=True, exist_ok=True)
    source_name = f"{uuid4().hex}.{suffix}"
    source_format = suffix
    extraction_format = CONVERTED_FORMATS.get(suffix, suffix)
    unit_type = {
        "pdf": "page",
        "docx": "paragraph",
        "pptx": "slide",
        "txt": "line",
        "doc": "paragraph",
        "ppt": "slide",
    }[suffix]
    final_path: Path | None = None
    valid = False
    try:
        # Le fichier source et le résultat converti restent dans un dossier temporaire.
        with tempfile.TemporaryDirectory(prefix="studyai-import-", dir=upload_dir) as temporary_dir:
            temporary_path = Path(temporary_dir)
            source_path = temporary_path / source_name
            size = 0
            with source_path.open("xb") as destination:
                # La lecture par blocs applique la limite même si le client ment sur la taille.
                while chunk := await file.read(64 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(
                            status_code=413, detail="Le document dépasse la taille autorisée."
                        )
                    destination.write(chunk)

            if suffix in LEGACY_FORMATS:
                converted_path = source_path.with_suffix(f".{extraction_format}")
                await _convert_legacy_office(
                    executable,
                    source_path,
                    converted_path,
                    conversion_timeout_seconds,
                )
                content_path = converted_path
            else:
                content_path = source_path

            if content_path.stat().st_size > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail="Le fichier converti dépasse la taille maximale autorisée.",
                )
            if extraction_format == "pdf":
                with content_path.open("rb") as source:
                    if source.read(len(PDF_MIME_HEADER)) != PDF_MIME_HEADER:
                        raise HTTPException(status_code=415, detail="Le fichier n'est pas un PDF valide.")
            elif extraction_format in OFFICE_REQUIRED_MEMBERS:
                _validate_office_archive(
                    content_path, extraction_format, max_archive_entries, max_expanded_bytes
                )
            else:
                try:
                    text = content_path.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError as exc:
                    raise HTTPException(
                        status_code=415, detail="Le fichier TXT doit être encodé en UTF-8."
                    ) from exc
                if "\x00" in text:
                    raise HTTPException(status_code=415, detail="Le fichier TXT contient des octets nuls.")

            units = extract_text_units(
                content_path, extraction_format, max_archive_entries, max_expanded_bytes
            )
            unit_count = len(units)
            has_text = any(unit.content.strip() for unit in units)
            if extraction_format == "pdf" and not has_text:
                processing_status = "ocr_required"
            else:
                processing_status = "pending_indexing" if has_text else "no_text"

            # Seul le fichier normalisé est gardé ; le document source est supprimé.
            storage_name = f"{uuid4().hex}.{extraction_format}"
            final_path = upload_dir / storage_name
            content_path.replace(final_path)
            valid = True
            return storage_name, source_format, unit_type, unit_count, processing_status
    finally:
        if final_path is not None and not valid:
            final_path.unlink(missing_ok=True)
        await file.close()
