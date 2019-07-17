"""Common utilities for VeSync Component."""
import logging
import asyncio
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vesync'

CONF_SWITCHES = 'switches'


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
            if not switch.dimmable_feature:
                devices[CONF_SWITCHES].append(switch)
        if manager.switches:
            _LOGGER.info(
                "%d VeSync standard switches found", len(manager.switches))

    return devices


async def async_add_devices(hass,
                            async_add_entities,
                            objects,
                            callback):
    """Add entities now and retry later if issues are encountered."""
    add_objects = objects.copy()

    async def process_objects(*args):

        for add_object in list(add_objects):

            try:
                _LOGGER.debug("Attempting to add object of type %s",
                              type(add_object))
                result = await hass.async_add_job(
                    callback,
                    add_object,
                    async_add_entities
                )
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.debug(str(ex))
                result = False

            if result is True or result is None:
                _LOGGER.debug("Added object")
                add_objects.remove(add_object)
            else:
                _LOGGER.debug("Failed to add object will try again")

    await process_objects()

    return True
