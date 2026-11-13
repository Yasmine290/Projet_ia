import re
from pathlib import Path
from uuid import uuid4

import pymupdf
from fastapi import HTTPException, UploadFile

from app.schemas.document import DocumentSegment


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


def extract_segments(
    path: Path, document_id: int, course_id: int, chunk_size: int
) -> list[DocumentSegment]:
    """Extrait chaque page et prépare ses segments, sans les indexer ni les stocker."""
    segments: list[DocumentSegment] = []
    try:
        with pymupdf.open(path) as pdf:
            if not pdf.is_pdf or pdf.needs_pass:
                raise HTTPException(status_code=422, detail="PDF protégé ou invalide.")
            for page_index, page in enumerate(pdf):
                page_number = page_index + 1
                for position, content in enumerate(split_text(page.get_text(), chunk_size)):
                    # Les identifiants sont reproductibles pour un même découpage.
                    segments.append(
                        DocumentSegment(
                            id=f"{document_id}:{page_number}:{position}",
                            document_id=document_id,
                            course_id=course_id,
                            page=page_number,
                            position=position,
                            content=content,
                        )
                    )
    except (pymupdf.FileDataError, pymupdf.EmptyFileError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail="PDF illisible ou inaccessible.") from exc
    if not segments:
        raise HTTPException(status_code=422, detail="Aucun texte détecté ; l'OCR n'est pas pris en charge.")
    return segments


async def store_pdf(file: UploadFile, upload_dir: Path, max_bytes: int) -> tuple[str, int, str]:
    """Valide et stocke un PDF sous un nom indépendant du nom fourni par le client."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Un fichier PDF est requis.")

    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid4().hex}.pdf"
    path = upload_dir / storage_name
    size = 0
    valid = False
    created = False
    try:
        # La lecture par blocs évite de charger tout le document en mémoire.
        with path.open("xb") as destination:
            created = True
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="Le PDF dépasse la taille autorisée.")
                destination.write(chunk)
        with path.open("rb") as source:
            if source.read(5) != b"%PDF-":
                raise HTTPException(status_code=415, detail="Le fichier n'est pas un PDF valide.")
        try:
            with pymupdf.open(path) as pdf:
                if not pdf.is_pdf or pdf.needs_pass:
                    raise HTTPException(status_code=422, detail="PDF protégé ou invalide.")
                if pdf.page_count < 1:
                    raise HTTPException(status_code=422, detail="Le PDF ne contient aucune page.")
                # L'OCR n'est pas disponible ; un PDF sans texte est signalé explicitement.
                has_text = any(page.get_text().strip() for page in pdf)
                page_count = pdf.page_count
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail="PDF illisible ou endommagé.") from exc
        valid = True
        return storage_name, page_count, "pending_indexing" if has_text else "ocr_required"
    finally:
        if created and not valid:
            path.unlink(missing_ok=True)
        await file.close()
