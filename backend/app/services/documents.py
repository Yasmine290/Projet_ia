from pathlib import Path
from uuid import uuid4

import pymupdf
from fastapi import HTTPException, UploadFile


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
