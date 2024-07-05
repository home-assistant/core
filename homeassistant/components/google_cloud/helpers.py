"""Helper classes for Google Cloud integration."""

from __future__ import annotations

from google.cloud import texttospeech


async def async_tts_voices(
    client: texttospeech.TextToSpeechAsyncClient,
) -> dict[str, list[str]]:
    """Get TTS voice model names keyed by language."""
    voices: dict[str, list[str]] = {}
    list_voices_response = await client.list_voices()
    for voice in list_voices_response.voices:
        language_code = voice.language_codes[0]
        if language_code not in voices:
            voices[language_code] = []
        voices[language_code].append(voice.name)
    return voices
