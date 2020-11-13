"""Support for Axis devices."""

import logging

from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP

from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Old way to set up Axis devices."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Axis component."""
    hass.data.setdefault(AXIS_DOMAIN, {})

    device = AxisNetworkDevice(hass, config_entry)

    if not await device.async_setup():
        return False

    # 0.104 introduced config entry unique id, this makes upgrading possible
    if config_entry.unique_id is None:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=device.api.vapix.serial_number
        )

    hass.data[AXIS_DOMAIN][config_entry.unique_id] = device

    await device.async_update_device_registry()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Axis device config entry."""
    device = hass.data[AXIS_DOMAIN].pop(config_entry.unique_id)
    return await device.async_reset()


async def async_migrate_entry(hass, config_entry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    #  Flatten configuration but keep old data if user rollbacks HASS prior to 0.106
    if config_entry.version == 1:
        config_entry.data = {**config_entry.data, **config_entry.data[CONF_DEVICE]}

        config_entry.version = 2

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
