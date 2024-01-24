"""The microBees integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .microbees import MicroBeesConnector

PLATFORMS: list[Platform] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up microBees from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    platforms = []

    if "connector" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["connector"] = MicroBeesConnector(
            token=entry.options.get(CONF_TOKEN)
        )

    microbees = hass.data[DOMAIN]["connector"]

    bees = await microbees.getBees()

    hass.data[DOMAIN]["bees"] = bees

    availablePlatforms = []
    for bee in bees:
        for sensor in bee.sensors:
            match sensor.device_type:
                case 0:
                    availablePlatforms.append(Platform.SWITCH)

        match bee.productID:
            case 46:
                availablePlatforms.append(Platform.SWITCH)

    platforms.extend(list(dict.fromkeys(availablePlatforms)))

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.options.get(CONF_TOKEN))

    return unload_ok
