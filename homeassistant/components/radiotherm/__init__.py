"""The radiotherm component."""
from __future__ import annotations

from socket import timeout

from radiotherm.validate import RadiothermTstatError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HOLD_TEMP, DOMAIN
from .coordinator import RadioThermUpdateCoordinator
from .data import async_get_init_data

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radio Thermostat from a config entry."""
    host = entry.data[CONF_HOST]
    try:
        init_data = await async_get_init_data(hass, host)
    except RadiothermTstatError as ex:
        raise ConfigEntryNotReady(
            f"{host} was busy (invalid value returned): {ex}"
        ) from ex
    except timeout as ex:
        raise ConfigEntryNotReady(
            f"{host} timed out waiting for a response: {ex}"
        ) from ex

    hold_temp = entry.options[CONF_HOLD_TEMP]
    coordinator = RadioThermUpdateCoordinator(hass, init_data, hold_temp)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
