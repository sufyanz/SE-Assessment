import asyncio
from pathlib import Path
from tempfile import NamedTemporaryFile

import whisper
from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="Audio Transcription API")

# Load the model once when the service starts.
model = whisper.load_model("base")

MAX_FILE_SIZE = 25 * 1024 * 1024
SUPPORTED_FORMATS = {".wav", ".mp3"}

# Limit simultaneous transcriptions per application process.
transcription_limit = asyncio.Semaphore(2)


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    filename = file.filename or "audio"
    suffix = Path(filename).suffix.lower()
    temp_path = None

    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Only WAV and MP3 files are supported.",
        )

    try:
        audio = await file.read(MAX_FILE_SIZE + 1)

        if not audio:
            raise HTTPException(400, "The uploaded file is empty.")

        if len(audio) > MAX_FILE_SIZE:
            raise HTTPException(413, "File size cannot exceed 25 MB.")

        with NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(audio)
            temp_path = Path(temp.name)

        # Keep CPU-intensive transcription off the event loop.
        async with transcription_limit:
            result = await asyncio.to_thread(
                model.transcribe,
                str(temp_path),
                fp16=False,
            )

        return {
            "success": True,
            "filename": filename,
            "language": result.get("language"),
            "full_text": result.get("text", "").strip(),
            "segments": [
                {
                    "start": round(segment["start"], 3),
                    "end": round(segment["end"], 3),
                    "text": segment["text"].strip(),
                }
                for segment in result.get("segments", [])
            ],
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Transcription failed. Please try again.",
        ) from exc
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)

        await file.close()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}