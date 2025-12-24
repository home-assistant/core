"""Common fixtures for the Fish Audio tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from fishaudio import AuthenticationError, FishAudioError
from fishaudio.exceptions import ServerError
import pytest

from homeassistant.components.fish_audio.const import (
    CONF_BACKEND,
    CONF_LATENCY,
    CONF_VOICE_ID,
    DOMAIN,
)
from homeassistant.components.fish_audio.error import (
    CannotGetModelsError,
    UnexpectedError,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

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
        ) as mock_client_class,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value

        # Mock account.get_credits()
        client.account.get_credits = AsyncMock(
            return_value=AsyncMock(user_id="test_user")
        )

        # Mock voices.list() with default voices
        mock_voice_1 = AsyncMock()
        mock_voice_1.id = "voice-alpha"
        mock_voice_1.title = "Alpha Voice"
        mock_voice_1.languages = ["en", "es"]
        mock_voice_1.task_count = 1000

        mock_voice_2 = AsyncMock()
        mock_voice_2.id = "voice-beta"
        mock_voice_2.title = "Beta Voice"
        mock_voice_2.languages = ["en", "zh"]
        mock_voice_2.task_count = 500

        client.voices.list = AsyncMock(
            return_value=AsyncMock(items=[mock_voice_1, mock_voice_2])
        )

        # Mock tts.convert()
        client.tts.convert = AsyncMock(return_value=b"fake_audio_data")

        yield client


@pytest.fixture
def mock_fishaudio_client_auth_error() -> Generator[AsyncMock]:
    """Mock AsyncFishAudio client with authentication error."""
    with (
        patch(
            "homeassistant.components.fish_audio.AsyncFishAudio",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.account.get_credits = AsyncMock(
            side_effect=AuthenticationError(401, "Invalid API key")
        )

        yield client


@pytest.fixture
def mock_fishaudio_client_connection_error() -> Generator[AsyncMock]:
    """Mock AsyncFishAudio client with connection error."""
    with (
        patch(
            "homeassistant.components.fish_audio.AsyncFishAudio",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.account.get_credits = AsyncMock(
            side_effect=FishAudioError("Connection error")
        )

        yield client


@pytest.fixture
def mock_fishaudio_client_server_error() -> Generator[AsyncMock]:
    """Mock AsyncFishAudio client with server error."""
    with (
        patch(
            "homeassistant.components.fish_audio.AsyncFishAudio",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.account.get_credits = AsyncMock(
            side_effect=ServerError(500, "Internal Server Error")
        )

        yield client


@pytest.fixture
def mock_fishaudio_client_voices_error() -> Generator[AsyncMock]:
    """Mock AsyncFishAudio client with voices.list() error."""
    with (
        patch(
            "homeassistant.components.fish_audio.AsyncFishAudio",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.account.get_credits = AsyncMock(
            return_value=AsyncMock(user_id="test_user")
        )
        client.voices.list = AsyncMock(
            side_effect=CannotGetModelsError(FishAudioError("API Error"))
        )

        yield client


@pytest.fixture
def mock_fishaudio_client_no_voices() -> Generator[AsyncMock]:
    """Mock AsyncFishAudio client that returns no voices."""
    with (
        patch(
            "homeassistant.components.fish_audio.AsyncFishAudio",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.account.get_credits = AsyncMock(
            return_value=AsyncMock(user_id="test_user")
        )
        client.voices.list = AsyncMock(return_value=AsyncMock(items=[]))

        yield client


@pytest.fixture
def mock_fishaudio_client_unknown_error() -> Generator[AsyncMock]:
    """Mock AsyncFishAudio client with unknown error."""
    with (
        patch(
            "homeassistant.components.fish_audio.AsyncFishAudio",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.fish_audio.config_flow.AsyncFishAudio",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.account.get_credits = AsyncMock(
            side_effect=UnexpectedError("Unexpected Error")
        )

        yield client
