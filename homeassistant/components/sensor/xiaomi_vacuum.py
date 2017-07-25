"""
Support for Xiaomi Vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sensor.xiaomi_vacuum/
"""
import asyncio

from homeassistant.components.vacuum.xiaomi_vacuum import (
    PLATFORM, CONF_HOST, CONF_NAME, CONF_SENSORS, MiroboVacuumSensor)


DEPENDENCIES = ['vacuum']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the vacuum switch from discovery info."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    name = discovery_info[CONF_NAME]
    sensors = discovery_info[CONF_SENSORS]
    mirobo_vacuum = hass.data[PLATFORM][host]

    async_add_devices(
        [MiroboVacuumSensor(mirobo_vacuum, name, s_type)
         for s_type in sensors], True)
