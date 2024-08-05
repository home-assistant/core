"""The Litter-Robot integration."""

from __future__ import annotations

from pylitterbot import FeederRobot, LitterRobot, LitterRobot3, LitterRobot4, Robot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .hub import LitterRobotHub

type LitterRobotConfigEntry = ConfigEntry[LitterRobotHub]

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


async def async_setup_entry(hass: HomeAssistant, entry: LitterRobotConfigEntry) -> bool:
    """Set up Litter-Robot from a config entry."""
    hub = LitterRobotHub(hass, entry.data)
    await hub.login(load_robots=True, subscribe_for_updates=True)
    entry.runtime_data = hub

    if platforms := get_platforms_for_robots(hub.account.robots):
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LitterRobotConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.account.disconnect()

    platforms = get_platforms_for_robots(entry.runtime_data.account.robots)
    return await hass.config_entries.async_unload_platforms(entry, platforms)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: LitterRobotConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        for robot in entry.runtime_data.account.robots
        if robot.serial == identifier[1]
    )
