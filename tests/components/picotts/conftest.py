"""Common fixtures for the Pico TTS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.picotts.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nanotts() -> Generator[MagicMock]:
    """Mock the NanoTTS engine."""
    with patch(
        "homeassistant.components.picotts.tts.NanoTTS", autospec=True
    ) as mock_class:
        engine = mock_class.return_value
        engine.speak.return_value = bytes(16000 * 2)
        yield engine
