"""
main.py
-------
FastAPI server para o PBIX Analyzer.
Serve a UI em static/index.html e expõe a API de upload/extração.
"""

import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from analyzer import build_payload, build_markdown

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="PBIX Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_pbix(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pbix"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .pbix são aceitos.")

    tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    try:
        with tmp_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        payload = build_payload(str(tmp_path))
        # Substitui nome do arquivo temporário pelo original
        payload["file"] = file.filename
        return JSONResponse(content=payload)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.post("/export-markdown")
async def export_markdown(file: UploadFile = File(...)):
    """Processa o .pbix e devolve o relatório Markdown como texto."""
    if not file.filename or not file.filename.lower().endswith(".pbix"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .pbix são aceitos.")

    tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    try:
        with tmp_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        payload = build_payload(str(tmp_path))
        payload["file"] = file.filename
        md = build_markdown(payload)
        return JSONResponse(content={"markdown": md})

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


if __name__ == "__main__":
    import webbrowser
    import uvicorn

    webbrowser.open("http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
