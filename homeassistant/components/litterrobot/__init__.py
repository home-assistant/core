"""The Litter-Robot integration."""
import asyncio

from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .hub import LitterRobotHub

PLATFORMS = ["vacuum"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Litter-Robot component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Litter-Robot from a config entry."""
    hub = hass.data[DOMAIN][entry.entry_id] = LitterRobotHub(hass, entry.data)
    try:
        await hub.login(load_robots=True)
    except LitterRobotLoginException:
        return False
    except LitterRobotException as ex:
        raise ConfigEntryNotReady from ex

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
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
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
