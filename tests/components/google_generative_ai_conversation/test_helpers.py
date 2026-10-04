"""Tests for the Google Generative AI Conversation helpers."""

from unittest.mock import Mock

import pytest

from homeassistant.components.google_generative_ai_conversation.helpers import (
    _parse_audio_mime_type,
    convert_to_wav,
    warmup_gaos,
)
from homeassistant.exceptions import HomeAssistantError


def test_parse_audio_mime_type_uppercase() -> None:
    """Test parsing uppercase MIME type audio/L16;rate=24000."""
    result = _parse_audio_mime_type("audio/L16;rate=24000")
    assert result == {"bits_per_sample": 16, "rate": 24000}


def test_parse_audio_mime_type_lowercase() -> None:
    """Test parsing lowercase MIME type audio/l16; rate=24000; channels=1."""
    result = _parse_audio_mime_type("audio/l16; rate=24000; channels=1")
    assert result == {"bits_per_sample": 16, "rate": 24000}


def test_parse_audio_mime_type_wav() -> None:
    """Test parsing audio/wav MIME type."""
    result = _parse_audio_mime_type("audio/wav")
    assert result == {"bits_per_sample": 16, "rate": 24000}


def test_parse_audio_mime_type_unsupported_raises() -> None:
    """Test that an unsupported MIME type raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        _parse_audio_mime_type("video/mp4")


def test_convert_to_wav_already_wav() -> None:
    """Test convert_to_wav returns existing wav audio unmodified."""
    raw_wav = b"RIFF1234WAVEfmt "
    assert convert_to_wav(raw_wav, "audio/wav") == raw_wav
    assert convert_to_wav(raw_wav, "audio/x-wav") == raw_wav
    assert convert_to_wav(raw_wav, "audio/unknown") == raw_wav


def test_convert_to_wav_raw_pcm() -> None:
    """Test convert_to_wav wraps raw pcm with wav header."""
    raw_pcm = b"\x00\x00" * 100
    converted = convert_to_wav(raw_pcm, "audio/l16;rate=24000")
    assert converted.startswith(b"RIFF")
    assert b"WAVE" in converted
    assert raw_pcm in converted


def test_warmup_gaos() -> None:
    """Test that warmup_gaos executes and warms up gaos modules."""
    mock_client = Mock()
    warmup_gaos(mock_client)
    _ = mock_client.aio.interactions
    # Second call should be idempotent
    warmup_gaos(mock_client)
