"""Tests for Prana integration entry points (async_setup_entry / async_unload_entry)."""

from homeassistant.components.prana.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import async_init_integration

from tests.common import SnapshotAssertion


async def test_async_setup_entry_and_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_prana_api
) -> None:
    """async_setup_entry should create coordinator, refresh it, store runtime_data and forward setups."""

    await async_init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_info_registered(
    hass: HomeAssistant,
    mock_config_entry,
    mock_prana_api,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Device info from the API should be registered on the device registry."""
    await async_init_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )

    assert device is not None
    assert snapshot == device
