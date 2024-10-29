"""Common utilities for VeSync Component."""

import logging

from .const import VS_FANS, VS_LIGHTS, VS_SENSORS, VS_SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_process_devices(hass, manager):
    """Assign devices to proper component."""
    devices = {}
    devices[VS_SWITCHES] = []
    devices[VS_FANS] = []
    devices[VS_LIGHTS] = []
    devices[VS_SENSORS] = []

    await hass.async_add_executor_job(manager.update)

    if manager.fans:
        devices[VS_FANS].extend(manager.fans)
        # Expose fan sensors separately
        devices[VS_SENSORS].extend(manager.fans)
        _LOGGER.debug("%d VeSync fans found", len(manager.fans))

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

    return devices
