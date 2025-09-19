"""Helper classes for Google Generative AI integration."""

from __future__ import annotations

from contextlib import suppress
import io
import wave

from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generate a WAV file header for the given audio data and parameters.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the WAV file header.

    """
    parameters = _parse_audio_mime_type(mime_type)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(parameters["bits_per_sample"] // 8)
        wf.setframerate(parameters["rate"])
        wf.writeframes(audio_data)

    return wav_buffer.getvalue()


# Below code is from https://aistudio.google.com/app/generate-speech
# when you select "Get SDK code to generate speech".
def _parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    """Parse bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys. Values will be
        integers if found, otherwise None.

    """
    if not mime_type.startswith("audio/L"):
        LOGGER.warning("Received unexpected MIME type %s", mime_type)
        raise HomeAssistantError(f"Unsupported audio MIME type: {mime_type}")

    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts:  # Skip the main type part
        param = param.strip()
        if param.lower().startswith("rate="):
            # Handle cases like "rate=" with no value or non-integer value and keep rate as default
            with suppress(ValueError, IndexError):
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
        elif param.startswith("audio/L"):
            # Keep bits_per_sample as default if conversion fails
            with suppress(ValueError, IndexError):
                bits_per_sample = int(param.split("L", 1)[1])

    return {"bits_per_sample": bits_per_sample, "rate": rate}
