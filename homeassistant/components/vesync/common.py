"""Common utilities for VeSync Component."""
import logging
from .const import CONF_SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_process_devices(hass, manager):
    """Assign devices to proper component."""
    devices = {}
    devices[CONF_SWITCHES] = []

    await hass.async_add_executor_job(manager.update)

    if manager.outlets:
        devices[CONF_SWITCHES].extend(manager.outlets)
        _LOGGER.info("%d VeSync outlets found", len(manager.outlets))

    if manager.switches:
        for switch in manager.switches:
            if not switch.is_dimmable():
                devices[CONF_SWITCHES].append(switch)
        _LOGGER.info(
            "%d VeSync standard switches found", len(manager.switches))

    return devices
