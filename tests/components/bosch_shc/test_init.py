"""Test the Bosch SHC integration setup and unload."""

from unittest.mock import MagicMock, patch

from boschshcpy.exceptions import SHCAuthenticationError, SHCConnectionError
import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


def _mock_session() -> MagicMock:
    """Build a mock SHCSession with a happy-path SHCInformation."""
    session = MagicMock()
    session.information.unique_id = "test-mac"
    session.information.updateState.name = "UP_TO_DATE"
    session.information.version = "2.0"
    return session


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """A successful setup creates the device and starts polling."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    mock_session = _mock_session()

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", []),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is mock_session
    mock_session.start_polling.assert_called_once()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test-mac")})
    assert device is not None
    assert device.manufacturer == "Bosch"
    assert device.model == "SmartHomeController"
    assert device.sw_version == "2.0"
    assert device.name == entry.title


async def test_setup_entry_auth_error_triggers_reauth(hass: HomeAssistant) -> None:
    """SHCAuthenticationError must surface as a setup error, not a retry."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        side_effect=SHCAuthenticationError,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_setup_entry_connection_error_retries(hass: HomeAssistant) -> None:
    """SHCConnectionError must be retryable, not a hard setup error."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        side_effect=SHCConnectionError,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_logs_update_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """An available SHC firmware update is surfaced via a log warning."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    mock_session = _mock_session()
    mock_session.information.updateState.name = "UPDATE_AVAILABLE"

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", []),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "check for software updates" in caplog.text


async def test_unload_entry_stops_polling(hass: HomeAssistant) -> None:
    """Unloading the entry stops the session's polling thread."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    mock_session = _mock_session()

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", []),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_session.stop_polling.assert_called_once()


async def test_homeassistant_stop_event_stops_polling(hass: HomeAssistant) -> None:
    """The session must stop polling on Home Assistant shutdown too, not only unload."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    mock_session = _mock_session()

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", []),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    mock_session.stop_polling.assert_called_once()


async def test_setup_entry_forwards_all_platforms(hass: HomeAssistant) -> None:
    """Every declared platform is forwarded during setup, not a hardcoded subset."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    mock_session = _mock_session()
    sentinel_platforms = [Platform.BUTTON, Platform.NUMBER]

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", sentinel_platforms),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=None,
        ) as mock_forward,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_forward.assert_awaited_once()
    forwarded_platforms = mock_forward.call_args.args[1]
    assert list(forwarded_platforms) == sentinel_platforms
