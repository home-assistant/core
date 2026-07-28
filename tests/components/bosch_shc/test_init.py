"""Test the Bosch SHC integration setup/unload (SHCSessionAsync)."""

from unittest.mock import AsyncMock, MagicMock, patch

from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
    SHCSessionError,
)
import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    "host": "1.1.1.1",
    "hostname": "shc012345",
    CONF_SSL_CERTIFICATE: "test-cert.pem",
    CONF_SSL_KEY: "test-key.pem",
}


def _mock_session() -> MagicMock:
    """Build a MagicMock standing in for SHCSessionAsync."""
    session = MagicMock()
    session.async_init = AsyncMock()
    session.start_polling = AsyncMock()
    session.stop_polling = AsyncMock()
    session.api.close = AsyncMock()
    session.information = MagicMock(
        unique_id="test-mac",
        version="1.0.0",
        update_state="NO_UPDATE_AVAILABLE",
    )
    return session


@pytest.fixture(autouse=True)
def mock_build_ssl_context() -> AsyncMock:
    """build_ssl_context() does blocking file I/O; stub it out."""
    with patch(
        "homeassistant.components.bosch_shc.build_ssl_context",
        return_value=MagicMock(),
    ) as mock_context:
        yield mock_context


async def test_setup_entry_success_closes_nothing(hass: HomeAssistant) -> None:
    """A clean setup leaves the session open and forwards the platforms."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-mac", data=MOCK_DATA)
    entry.add_to_hass(hass)

    session = _mock_session()
    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSessionAsync",
            return_value=session,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ) as mock_forward,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is session
    session.start_polling.assert_awaited_once()
    session.api.close.assert_not_called()
    mock_forward.assert_awaited_once()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)
    session.stop_polling.assert_awaited_once()


async def test_setup_entry_auth_failure_closes_session(hass: HomeAssistant) -> None:
    """An authentication error during async_init must close the session."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-mac", data=MOCK_DATA)
    entry.add_to_hass(hass)

    session = _mock_session()
    session.async_init.side_effect = SHCAuthenticationError

    with patch(
        "homeassistant.components.bosch_shc.SHCSessionAsync",
        return_value=session,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    session.api.close.assert_awaited_once()
    session.start_polling.assert_not_called()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(SHCConnectionError, id="connection_error"),
        pytest.param(SHCSessionError("boom"), id="session_error"),
    ],
)
async def test_setup_entry_init_connection_failure_closes_session(
    hass: HomeAssistant, exception: Exception
) -> None:
    """A connection/session error during async_init must close the session."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-mac", data=MOCK_DATA)
    entry.add_to_hass(hass)

    session = _mock_session()
    session.async_init.side_effect = exception

    with patch(
        "homeassistant.components.bosch_shc.SHCSessionAsync",
        return_value=session,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    session.api.close.assert_awaited_once()
    session.start_polling.assert_not_called()


async def test_setup_entry_polling_failure_closes_session(
    hass: HomeAssistant,
) -> None:
    """A failure to subscribe/start polling must close the session."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-mac", data=MOCK_DATA)
    entry.add_to_hass(hass)

    session = _mock_session()
    session.start_polling.side_effect = SHCConnectionError

    with patch(
        "homeassistant.components.bosch_shc.SHCSessionAsync",
        return_value=session,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    session.api.close.assert_awaited_once()


async def test_setup_entry_platform_forward_failure_stops_polling(
    hass: HomeAssistant,
) -> None:
    """A failure forwarding to platforms must stop the already-started polling."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-mac", data=MOCK_DATA)
    entry.add_to_hass(hass)

    session = _mock_session()

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSessionAsync",
            return_value=session,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            side_effect=RuntimeError,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    session.start_polling.assert_awaited_once()
    session.stop_polling.assert_awaited_once()
    session.api.close.assert_not_called()
