"""The OpenEVSE integration."""

from __future__ import annotations

from openevsehttp.__main__ import OpenEVSE

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator

PLATFORMS = [Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> bool:
    """Set up OpenEVSE from a config entry."""
    charger = OpenEVSE(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )

    try:
        await charger.test_and_get()
    except TimeoutError as ex:
        raise ConfigEntryNotReady("Unable to connect to charger") from ex

    coordinator = OpenEVSEDataUpdateCoordinator(hass, entry, charger)
    await coordinator.async_config_entry_first_refresh()

    # Start websocket listener for push updates
    coordinator.start_websocket()

    entry.runtime_data = coordinator

    # Register websocket cleanup on unload
    entry.async_on_unload(coordinator.async_stop_websocket)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
