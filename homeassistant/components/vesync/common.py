import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from .const import DOMAIN
import asyncio
from datetime import timedelta
_LOGGER = logging.getLogger(__name__)

CONF_LIGHTS = 'lights'
CONF_SWITCHES = 'switches'
CONF_FANS = 'fans'

class VesyncDevices:
    """Hold device lists"""
    def __init__(
            self,
            lights=None,
            switches=None,
            fans=None
        ):
        """Construct class"""
        self._lights = lights or []
        self._switches = switches or []
        self._fans = fans or []


async def async_process_devices(hass, manager):
    """Assign devices to proper component"""

    devices = {}
    devices[CONF_LIGHTS] = []
    devices[CONF_SWITCHES] = []
    devices[CONF_FANS] = []

    await hass.async_add_executor_job(manager.update)
    _LOGGER.debug(manager.bulbs)
    _LOGGER.debug(manager.switches)
    _LOGGER.debug(manager.outlets)
    if manager.bulbs:
        devices[CONF_LIGHTS].extend(manager.bulbs)
        _LOGGER.info("%d VeSync light bulbs found", len(manager.bulbs))

    if manager.fans:
        devices[CONF_FANS].extend(manager.fans)
        _LOGGER.info("%d VeSync fans found", len(manager.fans))

    if manager.switches:
        devices[CONF_SWITCHES].extend(manager.outlets)
        _LOGGER.info("%d VeSync outlets found", len(manager.switches))

    dim_switch = 0
    reg_switch = 0
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
    """Add entities now and retry later if issues are encountered"""

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
            except Exception as ex:
                _LOGGER.debug(str(ex))
                result = False

            if result is True or result is None:
                _LOGGER.debug("Added object")
                add_objects.remove(add_object)
            else:
                _LOGGER.debug("Failed to add object will try again")

    await process_objects_loop(interval.seconds)

    return cancel_interval_callback




async def async_rm_stale_devices(hass, manager):
    """Remove devices from HA that aren't found in account"""
    ha_list = hass.data[DOMAIN]
    ha_devices = ha_list.get(CONF_SWITCHES) + ha_list.get('lights')\
        + ha_list.get('fans')