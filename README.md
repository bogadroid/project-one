# StemStudio

A small local web app for separating songs into **vocals, drums, bass, and other** using the open-source Demucs `htdemucs` model. Upload a track, wait for the local model to process it, then preview and download each stem.

## Run locally

Requires Python 3.10+ and FFmpeg on your PATH. Demucs/PyTorch can take a while to install, and the first separation downloads the pretrained model. A machine with a supported GPU can accelerate processing; CPU works too, but may be slow.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:8000>. Uploads are limited to 100 MB. Audio is processed on your machine and is not sent to a third-party service. Files are stored in `data/` while the app runs; remove that folder to clear generated audio. Job status is held in memory, so restarting the server clears the job list.

## Notes

- This app uses the four-stem `htdemucs` model. Its `other` stem contains accompaniment that the model does not classify as vocals, drums, or bass; it does not isolate every individual instrument.
- Separation quality depends on the source recording and model. This is an independent project and is not affiliated with or endorsed by LALAL.AI.
- For production deployment, add persistent job storage, authentication, rate limiting, and upload lifecycle/retention controls. Do not expose this development server directly to the public internet.
