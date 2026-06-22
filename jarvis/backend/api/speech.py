"""Speech API endpoints: transcribe audio files and generate speech synthesis."""

import io
import os
import tempfile
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.ai.client import ai_client
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class TTSRequest(BaseModel):
    """Request payload for text-to-speech conversion."""
    text: str
    voice: str = "auq43ws1oslv0tO4BDa7"  # Default to user's ElevenLabs voice ID


@router.post("/stt", summary="Transcribe speech audio file to text")
async def transcribe_audio_file(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload an audio file and transcribe it to text using Gemini audio input.

    Args:
        file: Audio file attachment (e.g. WAV, MP3, WebM, M4A).

    Returns:
        Dict with "text" containing the transcription.
    """
    # Verify file is uploaded
    if not file:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")

    suffix = os.path.splitext(file.filename or "")[1] or ".wav"

    # Save the uploaded file to a temporary file
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"stt_upload_{os.urandom(8).hex()}{suffix}")

    try:
        # Save content asynchronously
        content = await file.read()
        with open(temp_file_path, "wb") as f:
            f.write(content)

        logger.info("Saved audio upload to %s (%d bytes). Starting Gemini transcription...", temp_file_path, len(content))

        # Transcribe using Gemini client
        text = await ai_client.transcribe_audio(temp_file_path)

        logger.info("Gemini transcription success: '%s'", text)
        return {"text": text}

    except Exception as exc:
        logger.error("Error during Gemini transcription: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError as cleanup_error:
                logger.warning("Failed to clean up temp speech file '%s': %s", temp_file_path, cleanup_error)


@router.post("/tts", summary="Convert text to synthetic speech audio")
async def text_to_speech_file(request: TTSRequest) -> StreamingResponse:
    """Convert text to speech audio stream using ElevenLabs TTS.

    Args:
        request: The text and voice to synthesize.

    Returns:
        Streaming response with synthesized audio.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text payload cannot be empty.")

    try:
        # Use ElevenLabs for TTS
        try:
            from elevenlabs import ElevenLabs

            api_key = settings.elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY", "")
            if not api_key or api_key == "your_elevenlabs_api_key_here":
                raise HTTPException(
                    status_code=500,
                    detail="ELEVENLABS_API_KEY not configured. Please set it in your .env file."
                )

            voice_id = request.voice if request.voice != "onyx" else settings.elevenlabs_voice_id

            logger.info("Generating TTS audio using ElevenLabs voice '%s' for text: '%s'", voice_id, request.text[:50])

            client = ElevenLabs(api_key=api_key)
            # generate() returns Iterator[bytes] in ElevenLabs SDK v1.x
            # — join the chunks into bytes before wrapping in BytesIO.
            audio_iter = client.generate(
                text=request.text,
                voice=voice_id,
                model="eleven_multilingual_v2"
            )
            audio_bytes = b"".join(audio_iter)

            # Stream the audio bytes back to the client
            return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")

        except ImportError:
            logger.error("ElevenLabs not installed, falling back to Gemini TTS")
            # Fallback to Gemini TTS if ElevenLabs is not available
            audio_bytes = await ai_client.generate_speech(request.text, voice=request.voice)
            return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error during TTS generation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
