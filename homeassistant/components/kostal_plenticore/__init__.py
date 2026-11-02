"""The Kostal Plenticore Solar Inverter integration."""

import logging

from pykoplenti import ApiException

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN
from .coordinator import Plenticore, PlenticoreConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: PlenticoreConfigEntry) -> None:
    """Set up Kostal Plenticore Solar Inverter from a config entry."""
    plenticore = Plenticore(hass, entry)

    if not await plenticore.async_setup():
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
            translation_placeholders={"host": plenticore.host},
        )

    entry.runtime_data = plenticore

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: PlenticoreConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    try:
        await entry.runtime_data.async_unload()
    except ApiException as err:
        _LOGGER.error("Error logging out from inverter: %s", err)
