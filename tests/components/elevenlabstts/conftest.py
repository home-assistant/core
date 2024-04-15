"""Common fixtures for the ElevenLabs text-to-speech tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from elevenlabs.core import ApiError
from elevenlabs.types import GetVoicesResponse, Model, Voice
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.elevenlabstts.async_setup_entry", return_value=True
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
                name="voice1",
            ),
            Voice(
                voice_id="voice2",
                name="voice2",
            ),
        ]
    )

    client_mock.models.get_all.return_value = [
        Model(
            model_id="model1",
            name="model1",
        ),
        Model(
            model_id="model2",
            name="model2",
        ),
    ]

    with patch(
        "homeassistant.components.elevenlabstts.config_flow.AsyncElevenLabs",
        return_value=client_mock,
    ) as mock_async_client:
        yield mock_async_client


@pytest.fixture
def mock_async_client_fail() -> Generator[AsyncMock, None, None]:
    """Override async ElevenLabs client."""
    with patch(
        "homeassistant.components.elevenlabstts.config_flow.AsyncElevenLabs",
        return_value=AsyncMock(),
    ) as mock_async_client:
        mock_async_client.side_effect = ApiError
        yield mock_async_client
