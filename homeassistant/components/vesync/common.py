"""Common utilities for VeSync Component."""

import logging
from typing import Any

from pyvesync import VeSync
from pyvesync.vesyncfan import VeSyncHumid200300S, VeSyncSuperior6000S

from homeassistant.core import HomeAssistant

from .const import VS_FANS, VS_HUMIDIFIERS, VS_LIGHTS, VS_SENSORS, VS_SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_process_devices(hass: HomeAssistant, manager: VeSync):
    """Assign devices to proper component."""
    devices: dict[str, Any] = {}
    devices[VS_SWITCHES] = []
    devices[VS_FANS] = []
    devices[VS_LIGHTS] = []
    devices[VS_SENSORS] = []
    devices[VS_HUMIDIFIERS] = []

    await hass.async_add_executor_job(manager.update)

    if manager.fans:
        # Expose fan sensors separately
        devices[VS_SENSORS].extend(manager.fans)
        _LOGGER.debug("%d VeSync fans found", len(manager.fans))

        for fan in manager.fans:
            devices[VS_HUMIDIFIERS if is_humidifier(fan) else VS_FANS].append(fan)

    if manager.bulbs:
        devices[VS_LIGHTS].extend(manager.bulbs)
        _LOGGER.debug("%d VeSync lights found", len(manager.bulbs))

    if manager.outlets:
        devices[VS_SWITCHES].extend(manager.outlets)
        # Expose outlets' voltage, power & energy usage as separate sensors
        devices[VS_SENSORS].extend(manager.outlets)
        _LOGGER.debug("%d VeSync outlets found", len(manager.outlets))

    if manager.switches:
        for switch in manager.switches:
            if not switch.is_dimmable():
                devices[VS_SWITCHES].append(switch)
            else:
                devices[VS_LIGHTS].append(switch)
        _LOGGER.debug("%d VeSync switches found", len(manager.switches))

    # Evaluate humidifier devices for dependent entities
    if devices[VS_HUMIDIFIERS]:
        devices[VS_SWITCHES].extend(devices[VS_HUMIDIFIERS])

    return devices


def is_humidifier(device) -> bool:
    """Check if the device represents a humidifier."""

    # VeSyncHumid200300S is the base for all humidifiers except VeSyncSuperior6000S.
    return isinstance(device, (VeSyncHumid200300S, VeSyncSuperior6000S))


def has_feature(device, dictionary, attribute):
    """Return the detail of the attribute."""
    return getattr(device, dictionary, {}).get(attribute, None) is not None
