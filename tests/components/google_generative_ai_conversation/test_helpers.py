"""Tests for the Google Generative AI Conversation helpers."""

from __future__ import annotations

import pytest

from homeassistant.components.google_generative_ai_conversation.helpers import (
    _parse_audio_mime_type,
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


def test_parse_audio_mime_type_unsupported_raises() -> None:
    """Test that an unsupported MIME type raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        _parse_audio_mime_type("video/mp4")
