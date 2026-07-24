"""Test the Bosch SHC integration setup and unload."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy.exceptions import SHCAuthenticationError, SHCConnectionError
import pytest

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to forwarding no platforms by default."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", []):
        yield


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """A successful setup creates the device and starts polling."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_session
    mock_session.start_polling.assert_called_once()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test-mac")})
    assert device is not None
    assert device.manufacturer == "Bosch"
    assert device.model == "SmartHomeController"
    assert device.sw_version == "2.0"
    assert device.name == mock_config_entry.title


async def test_setup_entry_auth_error_triggers_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """SHCAuthenticationError must surface as a setup error, not a retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        side_effect=SHCAuthenticationError,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_setup_entry_connection_error_retries(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """SHCConnectionError must be retryable, not a hard setup error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        side_effect=SHCConnectionError,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("mock_session", ["UPDATE_AVAILABLE"], indirect=True)
async def test_setup_entry_logs_update_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An available SHC firmware update is surfaced via a log warning."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert "check for software updates" in caplog.text


async def test_unload_entry_stops_polling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Unloading the entry stops the session's polling thread."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_session.stop_polling.assert_called_once()


async def test_homeassistant_stop_event_stops_polling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """The session must stop polling on Home Assistant shutdown too, not only unload."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    mock_session.stop_polling.assert_called_once()


async def test_setup_entry_forwards_all_platforms(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Every declared platform is forwarded during setup, not a hardcoded subset."""
    mock_config_entry.add_to_hass(hass)
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
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_forward.assert_awaited_once()
    forwarded_platforms = mock_forward.call_args.args[1]
    assert list(forwarded_platforms) == sentinel_platforms
