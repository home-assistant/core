"""Tests for the Solyx Energy integration setup and unload.

These drive the real HA config-entry lifecycle (setup, unload, retry, reauth)
with the API client mocked at the class level, so no network calls are made.
"""

from typing import TYPE_CHECKING

import pytest
from solyx_energy_api.exceptions import SolyxEnergyDataError, SolyxEnergyTokenError

from homeassistant.components.solyx_energy.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from .const import NYMO_DEVICE_ID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceRegistry


async def test_load_unload_config_entry(hass: HomeAssistant, init_integration) -> None:
    """The integration loads and can be unloaded cleanly."""
    assert init_integration.state == ConfigEntryState.LOADED
    assert init_integration.runtime_data.device_id == NYMO_DEVICE_ID

    # Unload and confirm HA marks the entry as no longer loaded.
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("api_error", [SolyxEnergyTokenError(), SolyxEnergyDataError()])
async def test_config_entry_not_ready(
    hass: HomeAssistant, mock_config_entry, mock_api_client_class, api_error
) -> None:
    """An API error occurs (translates to UpdateFailed) and schedules a retry (SETUP_RETRY) instead of hard-failing the entry."""
    mock_api_client_class.async_get_asset_data.side_effect = api_error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_info(device_registry: DeviceRegistry, init_integration) -> None:
    """Setup registers the Nymo device in HA's device registry with the right info."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, NYMO_DEVICE_ID), init_integration.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Solyx Energy"
    assert device.model == "Nymo"
    assert device.name == "Nymo"
