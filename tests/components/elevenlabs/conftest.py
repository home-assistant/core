"""Common fixtures for the ElevenLabs text-to-speech tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from elevenlabs.core import ApiError
from elevenlabs.types import GetVoicesResponse, LanguageResponse, Model, Voice
import pytest

from homeassistant.components.elevenlabs.const import DEFAULT_MODEL

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
    client_mock.voices.get_all.return_value = GetVoicesResponse(
        voices=[
            Voice(
                voice_id="voice1",
                name="Voice 1",
            ),
            Voice(
                voice_id="voice2",
                name="Voice 2",
            ),
        ]
    )
    models = [
        Model(
            model_id=f"model{i+1}",
            name=f"Model {i+1}",
            can_do_text_to_speech=True,
            languages=[
                LanguageResponse(language_id="en", name="English"),
                LanguageResponse(language_id="de", name="German"),
                LanguageResponse(language_id="es", name="Spanish"),
                LanguageResponse(language_id="ja", name="Japanese"),
            ],
        )
        for i in range(2)
    ]
    models.append(
        Model(
            model_id=DEFAULT_MODEL,
            name=DEFAULT_MODEL,
            can_do_text_to_speech=True,
            languages=[
                LanguageResponse(language_id="en", name="English"),
                LanguageResponse(language_id="de", name="German"),
                LanguageResponse(language_id="es", name="Spanish"),
                LanguageResponse(language_id="ja", name="Japanese"),
            ],
        )
    )
    client_mock.models.get_all.return_value = models
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
