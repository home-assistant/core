"""Common fixtures for the Fish Audio tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from fishaudio.resources import AsyncAccountClient, AsyncTTSClient, AsyncVoicesClient
import pytest

from homeassistant.components.fish_audio.const import (
    CONF_BACKEND,
    CONF_LATENCY,
    CONF_VOICE_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import MOCK_CREDITS, MOCK_VOICES

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fish_audio.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryDataWithId]:
    """Fixture for subentries."""
    return [
        ConfigSubentryDataWithId(
            data={
                CONF_VOICE_ID: "voice-123",
                CONF_BACKEND: "s1",
                CONF_LATENCY: "balanced",
            },
            subentry_type="tts",
            title="Test Voice",
            subentry_id="test-subentry-id",
            unique_id="voice-123-s1",
        ),
        ConfigSubentryDataWithId(
            data={
                CONF_VOICE_ID: "voice-beta",
                CONF_BACKEND: "s1",
                CONF_LATENCY: "normal",
            },
            subentry_type="tts",
            title="Second Voice",
            subentry_id="test-subentry-id-2",
            unique_id="voice-beta-s1",
        ),
    ]


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_subentries: list[ConfigSubentryDataWithId]
) -> MockConfigEntry:
    """Fixture for a config entry with subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Fish Audio",
        data={CONF_API_KEY: "test-api-key"},
        unique_id="test_user",
        entry_id="test-entry-id",
        subentries_data=[*mock_subentries],
    )


@pytest.fixture
def mock_fishaudio_client() -> Generator[AsyncMock]:
    """Mock AsyncFishAudio client."""
    with (
        patch(
            "homeassistant.components.fish_audio.AsyncFishAudio",
            autospec=True,
        ) as client_mock,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.account = AsyncMock(spec=AsyncAccountClient)
        client.account.get_credits.return_value = MOCK_CREDITS
        client.voices = AsyncMock(spec=AsyncVoicesClient)
        client.voices.list.return_value = AsyncMock(items=MOCK_VOICES)
        client.tts = AsyncMock(spec=AsyncTTSClient)
        client.tts.convert.return_value = b"fake_audio_data"
        yield client
