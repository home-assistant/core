"""The Kostal Plenticore Solar Inverter integration."""
import logging

from kostal.plenticore import PlenticoreApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helper import Plenticore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kostal Plenticore Solar Inverter from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    plenticore = Plenticore(hass, entry)

    if not await plenticore.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = plenticore

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # remove API object
        plenticore = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await plenticore.async_unload()
        except PlenticoreApiException as err:
            _LOGGER.error("Error logging out from inverter: %s", err)

    return unload_ok
