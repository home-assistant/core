"""The Kostal Plenticore Solar Inverter integration."""
import asyncio
import logging

from kostal.plenticore import PlenticoreApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helper import Plenticore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Kostal Plenticore Solar Inverter component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kostal Plenticore Solar Inverter from a config entry."""

    plenticore = Plenticore(hass, entry)

    if not await plenticore.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = plenticore

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        # remove API object
        plenticore = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await plenticore.async_unload()
        except PlenticoreApiException as err:
            _LOGGER.error("Error logging out from inverter: %s", err)

    return unload_ok
