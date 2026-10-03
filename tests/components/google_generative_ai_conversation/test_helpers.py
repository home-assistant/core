"""Tests for the Google Generative AI Conversation helpers."""

import io
import wave

import pytest

from homeassistant.components.google_generative_ai_conversation.helpers import (
    _parse_audio_mime_type,
    convert_to_wav,
)
from homeassistant.exceptions import HomeAssistantError


def _make_wav(frames: bytes, rate: int = 24000) -> bytes:
    """Create a WAV container around the given 16-bit mono PCM frames."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "mime_type", ["audio/wav", "audio/x-wav", "audio/wave", "audio/WAV; rate=24000"]
)
def test_convert_to_wav_passthrough_wav_mime_type(mime_type: str) -> None:
    """Test that data that is already a WAV container is returned unchanged."""
    wav = _make_wav(b"\x00\x01" * 100)
    assert convert_to_wav(wav, mime_type) == wav


def test_convert_to_wav_passthrough_riff_header() -> None:
    """Test that data with a RIFF/WAVE header is returned unchanged."""
    wav = _make_wav(b"\x00\x01" * 100)
    assert convert_to_wav(wav, "application/octet-stream") == wav


def test_convert_to_wav_raw_pcm() -> None:
    """Test that raw PCM data is wrapped in a WAV container."""
    pcm = b"\x00\x01" * 100
    assert convert_to_wav(pcm, "audio/L16;rate=24000") == _make_wav(pcm)


def test_convert_to_wav_unsupported_raises() -> None:
    """Test that an unsupported MIME type without a WAV header raises."""
    with pytest.raises(HomeAssistantError, match="Unsupported audio MIME type"):
        convert_to_wav(b"not-a-wav", "audio/mpeg")


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
