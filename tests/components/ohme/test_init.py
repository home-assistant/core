"""Test init of Ohme integration."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.components.ohme.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device(
    mock_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot the device from registry."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device({(DOMAIN, mock_client.serial)})
    assert device
    assert device == snapshot
