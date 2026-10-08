"""Tests for the Google Generative AI Conversation helpers."""

import io
import wave

import pytest

from homeassistant.components.google_generative_ai_conversation.helpers import (
    _parse_audio_mime_type,
    convert_to_wav,
)
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    "mime_type",
    [
        pytest.param("audio/wav", id="wav"),
        pytest.param("audio/wave", id="wave"),
        pytest.param("audio/x-wav", id="x-wav"),
        pytest.param("Audio/WAV; rate=24000", id="mixed-case-with-parameters"),
    ],
)
def test_convert_to_wav_returns_wav_data_unchanged(mime_type: str) -> None:
    """Test that audio data that is already a WAV file is returned as is."""
    # deliberately not a valid WAV file, so only the MIME type decides
    audio_data = b"wav-file-data"
    assert convert_to_wav(audio_data, mime_type) == audio_data


def test_convert_to_wav_wraps_raw_pcm() -> None:
    """Test that raw PCM audio data is wrapped in a WAV file."""
    pcm_data = b"\x00\x01" * 100
    result = convert_to_wav(pcm_data, "audio/L16;rate=24000")
    with wave.open(io.BytesIO(result)) as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 24000
        assert wav_file.readframes(wav_file.getnframes()) == pcm_data


def test_convert_to_wav_unsupported_mime_type_raises() -> None:
    """Test that an unsupported MIME type raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError, match="Unsupported audio MIME type"):
        convert_to_wav(b"audio-data", "audio/mpeg")


def test_parse_audio_mime_type_uppercase() -> None:
    """Test parsing uppercase MIME type audio/L16;rate=24000."""
    result = _parse_audio_mime_type("audio/L16;rate=24000")
    assert result == {"bits_per_sample": 16, "rate": 24000}


def test_parse_audio_mime_type_lowercase() -> None:
    """Test parsing lowercase MIME type audio/l16; rate=24000; channels=1."""
    result = _parse_audio_mime_type("audio/l16; rate=24000; channels=1")
    assert result == {"bits_per_sample": 16, "rate": 24000}


def test_parse_audio_mime_type_unsupported_raises() -> None:
    """Test that an unsupported MIME type raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        _parse_audio_mime_type("video/mp4")
