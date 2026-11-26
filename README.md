# StemStudio

StemStudio is a local web app for separating songs with the open-source Demucs `htdemucs_6s` model. It provides **six model-separated tracks**—vocals, drums, bass, guitar, piano, and other—plus a seventh downloadable **instrumental mix** made by combining the five non-vocal model stems. The instrumental mix is not a seventh independently AI-separated instrument; `other` can contain multiple instruments that the model does not classify separately.

## Run locally

Requires Python 3.10+ and FFmpeg on your PATH. Demucs/PyTorch can take a while to install, and the first separation downloads the pretrained model. A supported GPU can accelerate processing; CPU works too, but may be slow. The six-stem model needs more resources and takes longer than the four-stem model.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:8000>. Uploads are limited to 100 MB. Audio is processed locally and is not sent to a third-party service. Files are stored in `data/`; remove that folder to clear generated audio. Job status is held in memory, so restarting the server clears the job list.

## What the seven tracks mean

- **Vocals, drums, bass, guitar, piano, other** are the six categories produced by HTDemucs 6-stem.
- **Instrumental mix** combines the five non-vocal stems for convenient listening and download. It overlaps with those stems and is not a distinct seventh instrument.
- AI separation is not perfect. The `other` category is a catch-all, not a promise to isolate every instrument in a recording.

This is an independent project and is not affiliated with or endorsed by LALAL.AI. For public production deployment, add persistent job storage, authentication, rate limiting, and upload lifecycle/retention controls. Do not expose this development server directly to the public internet.
