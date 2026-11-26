from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("STEMSTUDIO_DATA", ROOT / "data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "separated"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aiff", ".aif"}
# HTDemucs 6-stem produces six model-separated categories. The seventh
# downloadable track is a useful instrumental mix derived from the non-vocal stems.
MODEL_STEMS = ("vocals", "drums", "bass", "guitar", "piano", "other")
DOWNLOAD_STEMS = (*MODEL_STEMS, "instrumental")

for directory in (UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="StemStudio", description="Separate songs into six model stems and an instrumental mix.")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
jobs: dict[str, dict[str, Any]] = {}


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": "htdemucs_6s", "downloadable_tracks": str(len(DOWNLOAD_STEMS))}


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


def create_instrumental(stem_dir: Path) -> None:
    """Mix the five non-vocal HTDemucs stems into a separate instrumental file."""
    tracks: list[np.ndarray] = []
    sample_rate: int | None = None
    for name in ("drums", "bass", "guitar", "piano", "other"):
        path = stem_dir / f"{name}.wav"
        if not path.is_file():
            continue
        audio, rate = sf.read(path, dtype="float32", always_2d=True)
        if sample_rate is None:
            sample_rate = rate
        if rate != sample_rate:
            raise RuntimeError("The model returned stems with mismatched sample rates.")
        tracks.append(audio)

    if not tracks or sample_rate is None:
        raise RuntimeError("Could not build the instrumental mix from the separated stems.")
    frames = min(track.shape[0] for track in tracks)
    channels = min(track.shape[1] for track in tracks)
    mix = np.sum([track[:frames, :channels] for track in tracks], axis=0, dtype=np.float32)
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.999:
        mix *= 0.999 / peak
    sf.write(stem_dir / "instrumental.wav", mix, sample_rate, subtype="PCM_24")


async def run_separation(job_id: str, upload_path: Path) -> None:
    jobs[job_id]["status"] = "processing"
    jobs[job_id]["progress"] = 5
    job_output = OUTPUT_DIR / job_id
    job_output.mkdir(parents=True, exist_ok=True)
    try:
        process = await asyncio.create_subprocess_exec(
            "python", "-m", "demucs.separate", "-n", "htdemucs_6s",
            "--out", str(job_output), str(upload_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        jobs[job_id]["progress"] = 15
        output, _ = await process.communicate()
        if process.returncode != 0:
            message = output.decode(errors="replace")[-1600:]
            raise RuntimeError(message or "The separation process failed.")

        stem_dir = next((path.parent for path in job_output.rglob("vocals.wav")), None)
        if stem_dir is None:
            raise RuntimeError("The model finished but did not produce its expected stems.")
        missing = [stem for stem in MODEL_STEMS if not (stem_dir / f"{stem}.wav").is_file()]
        if missing:
            raise RuntimeError("The model output was incomplete: " + ", ".join(missing))

        jobs[job_id]["progress"] = 90
        create_instrumental(stem_dir)
        jobs[job_id].update({
            "status": "complete",
            "progress": 100,
            "stems": {stem: f"/api/jobs/{job_id}/stems/{stem}" for stem in DOWNLOAD_STEMS},
        })
    except Exception as exc:
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
    if stem not in DOWNLOAD_STEMS:
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
