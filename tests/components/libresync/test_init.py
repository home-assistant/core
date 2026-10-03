"""Tests for the LibreSync integration setup."""

from unittest.mock import MagicMock, patch

from aiolibresync import NotConnectedError

from homeassistant.components.libresync.const import CONNECT_TIMEOUT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import HOST, STATE, push

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test the entry connects on setup and disconnects on unload."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.async_connect.assert_awaited_once_with(timeout=CONNECT_TIMEOUT)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.async_disconnect.assert_awaited_once()


async def test_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test a hub that does not answer in time is retried."""
    mock_client.async_connect.side_effect = NotConnectedError("no answer")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == (
        f"The hub at {HOST} did not answer on ports 50006 and 7777"
    )
    assert mock_client.subscribers == []


async def test_device_updated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the model reaches the device when it arrives, and the serial never."""
    mock_client.state = STATE.evolve(serial=None, model=None)
    await setup_integration(hass, mock_config_entry)

    push(mock_client, STATE)
    await hass.async_block_till_done()
    [device] = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device.model == "Stereo Hub"
    assert device.serial_number is None


async def test_platform_failure_disconnects(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test a setup that fails after connecting leaves no client running."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=RuntimeError("boom"),
    ):
        await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_client.async_disconnect.assert_awaited_once()


async def test_device_keeps_identity_across_reload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a reload before the model is answered keeps it."""
    await setup_integration(hass, mock_config_entry)
    [device] = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device.model == "Stereo Hub"

    mock_client.state = STATE.evolve(serial=None, model=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [device] = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device.model == "Stereo Hub"
