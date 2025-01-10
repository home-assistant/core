"""Common utilities for VeSync Component."""

import logging

from pyvesync import VeSync
from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.core import HomeAssistant

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
