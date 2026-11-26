from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("STEMSTUDIO_DATA", ROOT / "data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "separated"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aiff", ".aif"}
STEMS = {"vocals", "drums", "bass", "other"}

for directory in (UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="StemStudio", description="Separate a song into four audio stems.")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

# Lightweight in-memory job registry; jobs run locally through Demucs.
jobs: dict[str, dict[str, Any]] = {}


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/separate", status_code=202)
async def create_separation(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> dict[str, str]:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Choose an MP3, WAV, FLAC, M4A, OGG, or AIFF audio file.")

    job_id = uuid.uuid4().hex
    upload_path = UPLOAD_DIR / f"{job_id}{extension}"
    size = 0
    try:
        with upload_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    destination.close()
                    upload_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="The maximum upload size is 100 MB.")
                destination.write(chunk)
    finally:
        await file.close()

    if size == 0:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="That file is empty.")

    jobs[job_id] = {"status": "queued", "progress": 0, "stems": {}, "error": None}
    background_tasks.add_task(run_separation, job_id, upload_path)
    return {"job_id": job_id, "status": "queued"}


async def run_separation(job_id: str, upload_path: Path) -> None:
    jobs[job_id]["status"] = "processing"
    jobs[job_id]["progress"] = 10
    job_output = OUTPUT_DIR / job_id
    job_output.mkdir(parents=True, exist_ok=True)
    try:
        # Demucs downloads its pretrained model the first time it runs.
        process = await asyncio.create_subprocess_exec(
            "python", "-m", "demucs.separate", "-n", "htdemucs",
            "--out", str(job_output), str(upload_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        if process.returncode != 0:
            message = output.decode(errors="replace")[-1600:]
            raise RuntimeError(message or "The separation process failed.")

        stem_files = {path.stem.lower(): path for path in job_output.rglob("*.wav")}
        found = {stem: path for stem, path in stem_files.items() if stem in STEMS}
        if not found:
            raise RuntimeError("The model finished but did not produce any stems.")

        jobs[job_id].update({
            "status": "complete",
            "progress": 100,
            "stems": {stem: f"/api/jobs/{job_id}/stems/{stem}" for stem in found},
        })
    except Exception as exc:  # Keep the error associated with this job for the UI.
        jobs[job_id].update({"status": "error", "error": str(exc)[-1600:]})
    finally:
        upload_path.unlink(missing_ok=True)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found. Restart the app and submit the song again.")
    return job


@app.get("/api/jobs/{job_id}/stems/{stem}")
async def download_stem(job_id: str, stem: str) -> FileResponse:
    if stem not in STEMS:
        raise HTTPException(status_code=404, detail="Stem not found.")
    if job_id not in jobs or jobs[job_id]["status"] != "complete":
        raise HTTPException(status_code=404, detail="Stem not ready.")
    matches = list((OUTPUT_DIR / job_id).rglob(f"{stem}.wav"))
    if not matches:
        raise HTTPException(status_code=404, detail="Stem file not found.")
    return FileResponse(matches[0], media_type="audio/wav", filename=f"{stem}.wav")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
