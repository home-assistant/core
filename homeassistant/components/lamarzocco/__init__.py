"""The La Marzocco integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import LmApiCoordinator
from .lm_client import LaMarzoccoClient
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor", "sensor", "water_heater", "button", "update"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the La Marzocco component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up La Marzocco as config entry."""

    lm = LaMarzoccoClient(hass, config_entry.data)

    hass.data[DOMAIN][config_entry.entry_id] = coordinator = LmApiCoordinator(hass, lm)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Set up global services.
    await async_setup_services(hass, config_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    coordinator.terminate_websocket()

    services = hass.services.async_services().get(DOMAIN)
    if services is not None:
        for service in list(services.keys()):
            hass.services.async_remove(DOMAIN, service)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        hass.data[DOMAIN] = {}

    return unload_ok
