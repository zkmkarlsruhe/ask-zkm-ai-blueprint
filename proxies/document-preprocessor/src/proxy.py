"""Document preprocessor — convert office files to clean text.

Sits in front of webui/'s document upload pipeline. When a user uploads a
.docx, .pptx, .xlsx, or scanned PDF to OpenWebUI, the raw file makes a poor
RAG citizen — the embeddings of "PK\\x03\\x04..." are useless. This proxy
extracts clean text first.

Two endpoints:
  POST /convert       — file in, plain text + structured metadata out
  POST /convert/pdf   — file in, PDF out (for archival or when you need
                        layout preserved before further processing)

This is a SKELETON. The actual conversion logic depends on what you have
available:

  - **Docling** (https://github.com/DS4SD/docling) — IBM's open-source
    converter. Pretty good for office files and scanned PDFs.
  - **LibreOffice headless** — for .docx/.pptx/.xlsx -> PDF, then a PDF text
    extractor. Slower, more reliable, no Python deps.
  - **Tesseract** — for OCR of scanned PDFs / images.
  - **Cloud APIs** — if your sovereignty model permits.

The marked sections below are where you wire in your converter of choice.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger("document-preprocessor")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
ACCEPTED_SUFFIXES = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".pdf", ".odt", ".rtf", ".txt"}

app = FastAPI(title="Document Preprocessor")


def _validate(upload: UploadFile, body: bytes) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ACCEPTED_SUFFIXES:
        raise HTTPException(415, f"Unsupported type: {suffix}")
    if len(body) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_FILE_SIZE_MB}MB limit")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(body)
    tmp.close()
    return Path(tmp.name)


# --------------------------------------------------------------------------
# CONVERT TO TEXT
# --------------------------------------------------------------------------

def _extract_text(path: Path) -> dict:
    """Return {'text': str, 'pages': int, 'metadata': dict}.

    REPLACE THIS with your real converter. The skeleton just reads .txt
    verbatim and stubs everything else, which is enough to wire up the rest
    of the stack and confirm uploads flow correctly before you add Docling
    or LibreOffice.
    """
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return {"text": path.read_text(errors="replace"), "pages": 1, "metadata": {}}

    # ---- WIRE IN YOUR REAL CONVERTER HERE -------------------------------
    # Examples:
    #
    # # docling:
    # from docling.document_converter import DocumentConverter
    # result = DocumentConverter().convert(str(path))
    # return {
    #     "text": result.document.export_to_markdown(),
    #     "pages": len(result.document.pages),
    #     "metadata": {"source_format": suffix},
    # }
    #
    # # LibreOffice + pdfminer:
    # subprocess.run(["soffice", "--headless", "--convert-to", "pdf", str(path)],
    #                check=True, cwd=path.parent)
    # pdf_path = path.with_suffix(".pdf")
    # from pdfminer.high_level import extract_text
    # return {"text": extract_text(str(pdf_path)), "pages": ..., "metadata": {}}
    # ---------------------------------------------------------------------

    return {
        "text": f"[skeleton: real converter not wired in for {suffix}]",
        "pages": 0,
        "metadata": {"warning": "skeleton — wire in your converter in src/proxy.py:_extract_text"},
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    body = await file.read()
    path = _validate(file, body)
    try:
        out = _extract_text(path)
        out["filename"] = file.filename
        return JSONResponse(out)
    finally:
        path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# CONVERT TO PDF
# --------------------------------------------------------------------------

@app.post("/convert/pdf")
async def convert_pdf(file: UploadFile = File(...)):
    body = await file.read()
    path = _validate(file, body)
    try:
        # ---- WIRE IN PDF CONVERSION HERE --------------------------------
        # Example with LibreOffice:
        # subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
        #                 "--outdir", str(path.parent), str(path)], check=True)
        # pdf_path = path.with_suffix(".pdf")
        # if not pdf_path.exists():
        #     raise HTTPException(500, "PDF conversion failed")
        # return FileResponse(pdf_path, media_type="application/pdf",
        #                     filename=Path(file.filename or "out.pdf").stem + ".pdf")
        # ----------------------------------------------------------------
        raise HTTPException(501, "PDF conversion not wired up — see src/proxy.py")
    finally:
        path.unlink(missing_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok", "accepted_types": sorted(ACCEPTED_SUFFIXES)}


def main() -> None:
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8082")))


if __name__ == "__main__":
    main()
