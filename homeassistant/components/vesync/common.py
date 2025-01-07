"""Common utilities for VeSync Component."""

import logging

from pyvesync import VeSync
from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.core import HomeAssistant

<<<<<<< HEAD
=======
from .const import (
    VS_FANS,
    VS_HUMIDIFIERS,
    VS_LIGHTS,
    VS_SENSORS,
    VS_SWITCHES,
    VeSyncHumidifierDevice,
)

>>>>>>> 7909a0828ce (Added humidifier entity)
_LOGGER = logging.getLogger(__name__)


async def async_generate_device_list(
    hass: HomeAssistant, manager: VeSync
) -> list[VeSyncBaseDevice]:
    """Assign devices to proper component."""
    devices: list[VeSyncBaseDevice] = []

    await hass.async_add_executor_job(manager.update)

    devices.extend(manager.fans)
    devices.extend(manager.bulbs)
    devices.extend(manager.outlets)
    devices.extend(manager.switches)

    return devices


def is_humidifier(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a humidifier."""

    # VeSyncHumid200300S is the base for all humidifiers except VeSyncSuperior6000S.
    return isinstance(device, VeSyncHumidifierDevice)
