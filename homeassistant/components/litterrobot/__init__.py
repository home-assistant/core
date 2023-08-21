"""The Litter-Robot integration."""
from __future__ import annotations

from pylitterbot import FeederRobot, LitterRobot, LitterRobot3, LitterRobot4, Robot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import LitterRobotHub

PLATFORMS_BY_TYPE = {
    Robot: (
        Platform.BINARY_SENSOR,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ),
    LitterRobot: (Platform.VACUUM,),
    LitterRobot3: (Platform.BUTTON, Platform.TIME),
    LitterRobot4: (Platform.UPDATE,),
    FeederRobot: (Platform.BUTTON,),
}


def get_platforms_for_robots(robots: list[Robot]) -> set[Platform]:
    """Get platforms for robots."""
    return {
        platform
        for robot in robots
        for robot_type, platforms in PLATFORMS_BY_TYPE.items()
        if isinstance(robot, robot_type)
        for platform in platforms
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Litter-Robot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hub = hass.data[DOMAIN][entry.entry_id] = LitterRobotHub(hass, entry.data)
    await hub.login(load_robots=True, subscribe_for_updates=True)

    if platforms := get_platforms_for_robots(hub.account.robots):
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    await hub.account.disconnect()

    platforms = get_platforms_for_robots(hub.account.robots)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
