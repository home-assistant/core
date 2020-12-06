"""The 1-Wire component."""
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, SUPPORTED_PLATFORMS
from .onewirehub import CannotConnect, OneWireHub


async def async_setup(hass, config):
    """Set up 1-Wire integrations."""
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Set up a 1-Wire proxy for a config entry."""
    hass.data.setdefault(DOMAIN, {})

    onewirehub = OneWireHub(hass)
    try:
        await onewirehub.initialize(config_entry)
    except CannotConnect as exc:
        raise ConfigEntryNotReady() from exc

    hass.data[DOMAIN][config_entry.unique_id] = onewirehub

    for component in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in SUPPORTED_PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.unique_id)
    return unload_ok
