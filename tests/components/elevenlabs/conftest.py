"""Common fixtures for the ElevenLabs text-to-speech tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from elevenlabs.core import ApiError
from elevenlabs.types import GetVoicesResponse
from httpx import ConnectError
import pytest

from homeassistant.components.elevenlabs.const import (
    CONF_MODEL,
    CONF_STT_AUTO_LANGUAGE,
    CONF_VOICE,
)
from homeassistant.const import CONF_API_KEY

from .const import MOCK_MODELS, MOCK_VOICES

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.elevenlabs.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


def _client_mock():
    client_mock = AsyncMock()
    client_mock.voices.get_all.return_value = GetVoicesResponse(voices=MOCK_VOICES)
    client_mock.models.list.return_value = MOCK_MODELS

    return client_mock


@pytest.fixture
def mock_async_client() -> Generator[AsyncMock]:
    """Override async ElevenLabs client."""
    with (
        patch(
            "homeassistant.components.elevenlabs.AsyncElevenLabs",
            return_value=_client_mock(),
        ) as mock_async_client,
        patch(
            "homeassistant.components.elevenlabs.config_flow.AsyncElevenLabs",
            new=mock_async_client,
        ),
        patch(
            "homeassistant.components.elevenlabs.tts.AsyncElevenLabs",
            new=mock_async_client,
        ),
    ):
        yield mock_async_client


@pytest.fixture
def mock_async_client_api_error() -> Generator[AsyncMock]:
    """Override async ElevenLabs client with ApiError side effect."""
    client_mock = _client_mock()
    api_error = ApiError()
    api_error.body = {
        "detail": {"status": "invalid_api_key", "message": "API key is invalid"}
    }
    client_mock.models.list.side_effect = api_error
    client_mock.voices.get_all.side_effect = api_error

    with (
        patch(
            "homeassistant.components.elevenlabs.AsyncElevenLabs",
            return_value=client_mock,
        ) as mock_async_client,
        patch(
            "homeassistant.components.elevenlabs.config_flow.AsyncElevenLabs",
            new=mock_async_client,
        ),
    ):
        yield mock_async_client


@pytest.fixture
def mock_async_client_voices_error() -> Generator[AsyncMock]:
    """Override async ElevenLabs client with ApiError side effect."""
    client_mock = _client_mock()
    api_error = ApiError()
    api_error.body = {
        "detail": {
            "status": "voices_unauthorized",
            "message": "API is unauthorized for voices",
        }
    }
    client_mock.voices.get_all.side_effect = api_error

    with patch(
        "homeassistant.components.elevenlabs.config_flow.AsyncElevenLabs",
        return_value=client_mock,
    ) as mock_async_client:
        yield mock_async_client


@pytest.fixture
def mock_async_client_models_error() -> Generator[AsyncMock]:
    """Override async ElevenLabs client with ApiError side effect."""
    client_mock = _client_mock()
    api_error = ApiError()
    api_error.body = {
        "detail": {
            "status": "models_unauthorized",
            "message": "API is unauthorized for models",
        }
    }
    client_mock.models.list.side_effect = api_error

    with patch(
        "homeassistant.components.elevenlabs.config_flow.AsyncElevenLabs",
        return_value=client_mock,
    ) as mock_async_client:
        yield mock_async_client


@pytest.fixture
def mock_async_client_connect_error() -> Generator[AsyncMock]:
    """Override async ElevenLabs client."""
    client_mock = _client_mock()
    client_mock.models.list.side_effect = ConnectError("Unknown")
    client_mock.voices.get_all.side_effect = ConnectError("Unknown")
    with (
        patch(
            "homeassistant.components.elevenlabs.AsyncElevenLabs",
            return_value=client_mock,
        ) as mock_async_client,
        patch(
            "homeassistant.components.elevenlabs.config_flow.AsyncElevenLabs",
            new=mock_async_client,
        ),
    ):
        yield mock_async_client


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="elevenlabs",
        data={
            CONF_API_KEY: "api_key",
        },
        options={
            CONF_MODEL: "model1",
            CONF_VOICE: "voice1",
            CONF_STT_AUTO_LANGUAGE: False,
        },
    )
    entry.models = {
        "model1": "model1",
    }

    entry.voices = {"voice1": "voice1"}
    return entry


@pytest.fixture(name="config_data")
def config_data_fixture() -> dict[str, Any]:
    """Return config data."""
    return {}


@pytest.fixture(name="config_options")
def config_options_fixture() -> dict[str, Any]:
    """Return config options."""
    return {}
