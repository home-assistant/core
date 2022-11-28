"""The Litter-Robot integration."""
from __future__ import annotations

from pylitterbot import FeederRobot, LitterRobot, LitterRobot3, LitterRobot4

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import LitterRobotHub

PLATFORMS = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]

PLATFORMS_BY_TYPE = {
    LitterRobot: (
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.VACUUM,
    ),
    LitterRobot3: (
        Platform.BUTTON,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.VACUUM,
    ),
    LitterRobot4: (
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.VACUUM,
    ),
    FeederRobot: (
        Platform.BUTTON,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Litter-Robot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hub = hass.data[DOMAIN][entry.entry_id] = LitterRobotHub(hass, entry.data)
    await hub.login(load_robots=True)

    platforms: set[str] = set()
    for robot in hub.account.robots:
        platforms.update(PLATFORMS_BY_TYPE[type(robot)])
    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    await hub.account.disconnect()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
