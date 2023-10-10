"""The La Marzocco integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LmApiCoordinator
from .lm_client import LaMarzoccoClient
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor", "sensor", "water_heater", "button"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the La Marzocco component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, config_entry):
    """Set up La Marzocco as config entry."""

    config_entry.async_on_unload(config_entry.add_update_listener(options_update_listener))

    lm = LaMarzoccoClient(hass, config_entry.data)

    hass.data[DOMAIN][config_entry.entry_id] = coordinator = LmApiCoordinator(hass, config_entry, lm)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    """Set up global services."""
    await async_setup_services(hass, config_entry)
    return True


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    coordinator.terminate_websocket()

    services = list(hass.services.async_services().get(DOMAIN).keys())
    [hass.services.async_remove(DOMAIN, service) for service in services]

    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        hass.data[DOMAIN] = {}

    return unload_ok
