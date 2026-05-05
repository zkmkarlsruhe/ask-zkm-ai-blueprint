# document-preprocessor/

A small HTTP service that converts uploaded office files to clean text (and
optionally PDF) before they enter your RAG pipeline.

## Why

When OpenWebUI ingests a `.docx` or scanned `.pdf`, what gets embedded is the
raw bytes interpreted as text — often garbage. Embeddings of garbage match
nothing useful. Pre-converting to clean markdown / plaintext makes the RAG
results dramatically better.

## What this skeleton does

- Accepts `POST /convert` with a multipart file upload.
- Validates type and size.
- **Stubs the actual extraction** — see `src/proxy.py:_extract_text`.

## Wire in a real converter

Two main options:

### Option A: Docling (recommended for richness)

```python
# In _extract_text:
from docling.document_converter import DocumentConverter
result = DocumentConverter().convert(str(path))
return {
    "text": result.document.export_to_markdown(),
    "pages": len(result.document.pages),
    "metadata": {"source_format": suffix},
}
```

Add `"docling>=2.0"` to `pyproject.toml`. Heavy dep (PyTorch); image gets
big. Worth it.

### Option B: LibreOffice + pdfminer (lighter, slower)

```python
# In _extract_text:
import subprocess
subprocess.run(
    ["soffice", "--headless", "--convert-to", "pdf",
     "--outdir", str(path.parent), str(path)],
    check=True, timeout=120,
)
pdf_path = path.with_suffix(".pdf")
from pdfminer.high_level import extract_text
return {"text": extract_text(str(pdf_path)), "pages": -1, "metadata": {}}
```

Uncomment the LibreOffice apt-get line in `Dockerfile`.

## Wire it to OpenWebUI

OWUI's document loaders are pluggable. The exact env vars vary per OWUI
version, but the pattern is:

1. Set OWUI's content extraction engine to "external".
2. Point it at this service: `CONTENT_EXTRACTION_ENGINE_URL=http://document-preprocessor:8082/convert`
3. Restart OWUI.

Test by uploading a `.docx` to a chat — you should see clean text in the
extracted content rather than binary noise.

## Test

```bash
docker compose up -d
echo "Hello world" > /tmp/test.txt
curl -F "file=@/tmp/test.txt" http://localhost:8082/convert
# -> {"text":"Hello world\n","pages":1,"metadata":{},"filename":"test.txt"}
```
