"""Tests for the Spin EV Charger integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.exicom_spin_ble.const import (
    CONF_CONNECTION_MODE,
    ConnectionMode,
)
from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the integration up from a config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def setup_persistent(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the integration up with the charger's Bluetooth slot held open."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_CONNECTION_MODE: ConnectionMode.PERSISTENT},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
