"""Tests for the Profalux Neosol setup and teardown."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyneosol import DongleNotFoundError, NotADongleError, ProtocolError, TransportError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.neosol.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_dongle")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_dongle: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and releases the serial port when unloaded."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_dongle.close.assert_not_awaited()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_dongle.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("failing_call", "exception"),
    [
        pytest.param("open", DongleNotFoundError("no such port"), id="no-port"),
        pytest.param("info", NotADongleError("no marker"), id="not-a-dongle"),
        pytest.param(
            "used_channels", TransportError("link died"), id="channel-table-failed"
        ),
    ],
)
async def test_setup_failure_retries(
    hass: HomeAssistant,
    mock_dongle_class: MagicMock,
    mock_config_entry: MockConfigEntry,
    failing_call: str,
    exception: Exception,
) -> None:
    """Test a dongle that cannot be reached puts the entry in retry."""
    target = (
        mock_dongle_class.open
        if failing_call == "open"
        else getattr(mock_dongle_class.open.return_value, failing_call)
    )
    target.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_port_released_when_first_refresh_fails(
    hass: HomeAssistant, mock_dongle: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the port is not left open when the first channel read fails."""
    mock_dongle.used_channels.side_effect = TransportError("link died")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_dongle.close.assert_awaited_once()


async def test_port_released_when_platform_setup_fails(
    hass: HomeAssistant, mock_dongle: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the port is not left open when the setup fails after the first read."""
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("boom"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_dongle.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_dongle")
async def test_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the dongle and its shutters are registered as devices."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert sorted(devices, key=lambda device: sorted(device.identifiers)) == snapshot


async def test_lost_link_reloads_the_entry(
    hass: HomeAssistant,
    mock_dongle_class: MagicMock,
    mock_dongle: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unplugged dongle hands the entry back to the setup retry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_dongle_class.open.call_count == 1

    mock_dongle.used_channels.side_effect = TransportError("link died")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Reopening the port is the only way back, so the entry is reloaded.
    assert mock_dongle_class.open.call_count == 2
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_channel_table_error_keeps_the_entry(
    hass: HomeAssistant,
    mock_dongle_class: MagicMock,
    mock_dongle: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a garbled answer only marks the shutters unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_dongle.used_channels.side_effect = ProtocolError("garbled answer")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The link is still up, so there is nothing a reload would fix.
    assert mock_dongle_class.open.call_count == 1
    assert hass.states.get("cover.shutter_0").state == STATE_UNAVAILABLE
