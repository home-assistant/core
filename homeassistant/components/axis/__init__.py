"""Support for Axis devices."""

import logging

from homeassistant.const import CONF_DEVICE, CONF_MAC, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_registry import async_migrate_entries

from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry):
    """Set up the Axis component."""
    hass.data.setdefault(AXIS_DOMAIN, {})

    device = AxisNetworkDevice(hass, config_entry)

    if not await device.async_setup():
        return False

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
        unique_id = config_entry.data[CONF_MAC]
        data = {**config_entry.data, **config_entry.data[CONF_DEVICE]}
        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id, data=data
        )
        config_entry.version = 2

    # Normalise MAC address of device which also affects entity unique IDs
    if config_entry.version == 2:
        old_unique_id = config_entry.unique_id
        new_unique_id = format_mac(old_unique_id)

        @callback
        def update_unique_id(entity_entry):
            """Update unique ID of entity entry."""
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old_unique_id, new_unique_id
                )
            }

        if old_unique_id != new_unique_id:
            await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

            hass.config_entries.async_update_entry(
                config_entry, unique_id=new_unique_id
            )

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
