"""Common fixtures for the Fish Audio tests."""

from collections.abc import Generator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fish_audio_sdk.exceptions import HttpCodeErr
from fish_audio_sdk.schemas import APICreditEntity
import pytest

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_BACKEND, CONF_VOICE_ID, DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fish_audio.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


def _get_session_mock() -> MagicMock:
    """Return a mock session."""
    session_mock = MagicMock()
    session_mock.get_api_credit.return_value = APICreditEntity(
        _id="test_id",
        user_id="test_user",
        credit=Decimal("100.0"),
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )
    return session_mock


@pytest.fixture
def mock_async_client(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Mock the async client."""
    with (
        patch(
            "homeassistant.components.fish_audio.config_flow.Session",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.fish_audio.Session",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_api_credit.return_value = APICreditEntity(
            _id="test_id",
            user_id="test_user",
            credit=Decimal("100.0"),
            created_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
        )
        yield mock_client


@pytest.fixture
def mock_tts_subentry() -> MagicMock:
    """Mock a TTS sub-entry."""
    mock_subentry = MagicMock(spec=ConfigSubentry)
    mock_subentry.subentry_id = "test-subentry"
    mock_subentry.subentry_type = "tts"
    mock_subentry.title = "Test TTS"
    mock_subentry.data = {CONF_VOICE_ID: "voice-123", CONF_BACKEND: "s1"}
    return mock_subentry


@pytest.fixture
def mock_config_entry(mock_tts_subentry: MagicMock) -> MockConfigEntry:
    """Mock a config entry with a TTS sub-entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123"},
        title="Fish Audio",
    )
    entry.subentries = {mock_tts_subentry.subentry_id: mock_tts_subentry}
    return entry


@pytest.fixture
def mock_async_client_connect_error() -> Generator[MagicMock]:
    """Override Session client with a connection error."""
    session_mock = _get_session_mock()
    session_mock.get_api_credit.side_effect = HttpCodeErr(500, "Server Error")
    with (
        patch(
            "homeassistant.components.fish_audio.Session",
            return_value=session_mock,
        ) as mock_session,
        patch(
            "homeassistant.components.fish_audio.config_flow.Session",
            new=mock_session,
        ),
    ):
        yield mock_session


@pytest.fixture
def mock_async_client_generic_error() -> Generator[MagicMock]:
    """Override Session client with a generic error."""
    session_mock = _get_session_mock()
    session_mock.get_api_credit.side_effect = Exception("Generic Error")
    with (
        patch(
            "homeassistant.components.fish_audio.Session",
            return_value=session_mock,
        ) as mock_session,
        patch(
            "homeassistant.components.fish_audio.config_flow.Session",
            new=mock_session,
        ),
    ):
        yield mock_session


@pytest.fixture
def mock_async_client_auth_error() -> Generator[MagicMock]:
    """Override Session client with an authentication error."""
    session_mock = _get_session_mock()
    session_mock.get_api_credit.side_effect = HttpCodeErr(401, "Auth Error")
    with (
        patch(
            "homeassistant.components.fish_audio.Session",
            return_value=session_mock,
        ) as mock_session,
        patch(
            "homeassistant.components.fish_audio.config_flow.Session",
            new=mock_session,
        ),
    ):
        yield mock_session


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_user",
        data={CONF_API_KEY: "test-api-key"},
        options={"voice_id": "1"},
        title="Fish Audio",
    )
