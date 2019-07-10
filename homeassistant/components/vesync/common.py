"""Common utilities for VeSync Component."""
import logging
import asyncio
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

CONF_LIGHTS = 'lights'
CONF_SWITCHES = 'switches'
CONF_FANS = 'fans'


async def async_process_devices(hass, manager):
    """Assign devices to proper component."""
    devices = {}
    devices[CONF_LIGHTS] = []
    devices[CONF_SWITCHES] = []
    devices[CONF_FANS] = []

    await hass.async_add_executor_job(manager.update)

    if manager.bulbs:
        devices[CONF_LIGHTS].extend(manager.bulbs)
        _LOGGER.info(str(devices[CONF_LIGHTS]))
        _LOGGER.info("%d VeSync light bulbs found", len(manager.bulbs))

    if manager.fans:
        devices[CONF_FANS].extend(manager.fans)
        _LOGGER.info("%d VeSync fans found", len(manager.fans))

    if manager.outlets:
        devices[CONF_SWITCHES].extend(manager.outlets)
        _LOGGER.info("%d VeSync outlets found", len(manager.switches))

    dim_switch = 0
    reg_switch = 0
    if manager.switches:
        for switch in manager.switches:
            if switch.is_dimmable():
                devices[CONF_LIGHTS].append(switch)
                dim_switch += 1
            else:
                devices[CONF_SWITCHES].append(switch)
                reg_switch += 1
        if dim_switch > 0:
            _LOGGER.info("%d VeSync dimmable switches found", dim_switch)
        if reg_switch > 0:
            _LOGGER.info("%d VeSync standard switches found", reg_switch)

    return devices


async def async_add_entities_retry(hass,
                                   async_add_entities,
                                   objects,
                                   callback,
                                   interval=timedelta(seconds=60)):
    """Add entities now and retry later if issues are encountered."""
    add_objects = objects.copy()

    is_cancelled = False

    def cancel_interval_callback():
        nonlocal is_cancelled
        is_cancelled = True

    async def process_objects_loop(delay: int):
        if is_cancelled:
            return

        await process_objects()

        if not add_objects:
            return

        await asyncio.sleep(delay)

        hass.async_create_task(process_objects_loop(delay))

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

    await process_objects_loop(interval.seconds)

    return cancel_interval_callback
