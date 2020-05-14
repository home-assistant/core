"""Support for Axis devices."""

import logging

from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TRIGGER_TIME,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)

from .const import CONF_CAMERA, CONF_EVENTS, DEFAULT_TRIGGER_TIME, DOMAIN
from .device import AxisNetworkDevice, get_device

LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Old way to set up Axis devices."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Axis component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not config_entry.options:
        await async_populate_options(hass, config_entry)

    device = AxisNetworkDevice(hass, config_entry)

    if not await device.async_setup():
        return False

    # 0.104 introduced config entry unique id, this makes upgrading possible
    if config_entry.unique_id is None:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=device.api.vapix.params.system_serialnumber
        )

    hass.data[DOMAIN][config_entry.unique_id] = device

    await device.async_update_device_registry()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Axis device config entry."""
    device = hass.data[DOMAIN].pop(config_entry.data[CONF_MAC])
    return await device.async_reset()


async def async_populate_options(hass, config_entry):
    """Populate default options for device."""
    device = await get_device(
        hass,
        host=config_entry.data[CONF_HOST],
        port=config_entry.data[CONF_PORT],
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
    )

    supported_formats = device.vapix.params.image_format
    camera = bool(supported_formats)

    options = {
        CONF_CAMERA: camera,
        CONF_EVENTS: True,
        CONF_TRIGGER_TIME: DEFAULT_TRIGGER_TIME,
    }

    hass.config_entries.async_update_entry(config_entry, options=options)


async def async_migrate_entry(hass, config_entry):
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    #  Flatten configuration but keep old data if user rollbacks HASS
    if config_entry.version == 1:
        config_entry.data = {**config_entry.data, **config_entry.data[CONF_DEVICE]}

        config_entry.version = 2

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
