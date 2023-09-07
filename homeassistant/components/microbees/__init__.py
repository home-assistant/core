""" Integration microBees """

import logging
from homeassistant.const import Platform, CONF_DOMAIN, CONF_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .servicesMicrobees import getBees

_LOGGER = logging.getLogger(__name__)

platforms = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up microBees from a config entry."""

    token = dict(entry.data)["token"]

    bees = await getBees(hass,token)

    entry.data = dict({"token": token, "bees": bees})

    for bee in bees:
        _LOGGER.info(bee)

        for actuator in bee.get("actuators"):
            match actuator.get("device_type"):
                case 0:
                    platforms.append(Platform.SWITCH)

        match bee.get("productID"):
            case 46:
                platforms.append(Platform.SWITCH)

    platforms = list(dict.fromkeys(platforms))

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[CONF_DOMAIN].pop(entry.entry_id)

    return unload_ok
