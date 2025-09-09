"""Common fixtures for the Fish Audio tests."""

from collections.abc import Generator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fish_audio_sdk.schemas import APICreditEntity
import pytest

from homeassistant.components.fish_audio.const import CONF_API_KEY, DOMAIN

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
def mock_async_client() -> Generator[MagicMock]:
    """Override Session."""
    with (
        patch(
            "homeassistant.components.fish_audio.Session",
            return_value=_get_session_mock(),
        ) as mock_session,
        patch(
            "homeassistant.components.fish_audio.config_flow.Session",
            new=mock_session,
        ),
        patch(
            "homeassistant.components.fish_audio.tts.Session",
            new=mock_session,
        ),
        patch(
            "homeassistant.components.fish_audio.stt.Session",
            new=mock_session,
        ),
    ):
        yield mock_session


@pytest.fixture
def mock_async_client_connect_error() -> Generator[MagicMock]:
    """Override Session client with a connection error."""
    session_mock = _get_session_mock()
    session_mock.get_api_credit.side_effect = Exception("Connection error")

    with (
        patch(
            "homeassistant.components.fish_audio.Session",
            return_value=session_mock,
        ) as mock_session,
        patch(
            "homeassistant.components.fish_audio.config_flow.Session",
            new=mock_session,
        ),
        patch(
            "homeassistant.components.fish_audio.tts.Session",
            new=mock_session,
        ),
        patch(
            "homeassistant.components.fish_audio.stt.Session",
            new=mock_session,
        ),
    ):
        yield mock_session


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        options={"voice_id": "1"},
        title="Fish Audio",
    )
