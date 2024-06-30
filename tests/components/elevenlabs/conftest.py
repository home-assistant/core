"""Common fixtures for the ElevenLabs text-to-speech tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from elevenlabs.core import ApiError
from elevenlabs.types import GetVoicesResponse
import pytest

from .const import MOCK_MODELS, MOCK_VOICES

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.elevenlabs.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_async_client() -> Generator[AsyncMock, None, None]:
    """Override async ElevenLabs client."""
    client_mock = AsyncMock()
    client_mock.voices.get_all.return_value = GetVoicesResponse(voices=MOCK_VOICES)
    client_mock.models.get_all.return_value = MOCK_MODELS
    with patch(
        "elevenlabs.client.AsyncElevenLabs", return_value=client_mock
    ) as mock_async_client:
        yield mock_async_client


@pytest.fixture
def mock_async_client_fail() -> Generator[AsyncMock, None, None]:
    """Override async ElevenLabs client."""
    with patch(
        "homeassistant.components.elevenlabs.config_flow.AsyncElevenLabs",
        return_value=AsyncMock(),
    ) as mock_async_client:
        mock_async_client.side_effect = ApiError
        yield mock_async_client


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain="elevenlabs",
        data={
            "api_key": "api_key",
            "model": "model1",
        },
    )
