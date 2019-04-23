"""Support for Axis devices."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_TRIGGER_TIME,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv

from .config_flow import configured_devices, DEVICE_SCHEMA
from .const import CONF_CAMERA, CONF_EVENTS, DEFAULT_TRIGGER_TIME, DOMAIN
from .device import AxisNetworkDevice, get_device

REQUIREMENTS = ['axis==17']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.schema_with_slug_keys(DEVICE_SCHEMA),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up for Axis devices."""
    if DOMAIN in config:

        for device_name, device_config in config[DOMAIN].items():

            if CONF_NAME not in device_config:
                device_config[CONF_NAME] = device_name

            if device_config[CONF_HOST] not in configured_devices(hass):
                hass.async_create_task(hass.config_entries.flow.async_init(
                    DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
                    data=device_config
                ))

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

    hass.data[DOMAIN][device.serial] = device

    await device.async_update_device_registry()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)

    return True


async def async_populate_options(hass, config_entry):
    """Populate default options for device."""
    from axis.vapix import VAPIX_IMAGE_FORMAT

    device = await get_device(hass, config_entry.data[CONF_DEVICE])

    supported_formats = device.vapix.get_param(VAPIX_IMAGE_FORMAT)

    camera = bool(supported_formats)

    options = {
        CONF_CAMERA: camera,
        CONF_EVENTS: True,
        CONF_TRIGGER_TIME: DEFAULT_TRIGGER_TIME
    }

    hass.config_entries.async_update_entry(config_entry, options=options)
