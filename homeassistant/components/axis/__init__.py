"""Support for Axis devices."""

from homeassistant.const import (
    CONF_DEVICE,
    CONF_MAC,
    CONF_TRIGGER_TIME,
    EVENT_HOMEASSISTANT_STOP,
)

from .const import CONF_CAMERA, CONF_EVENTS, DEFAULT_TRIGGER_TIME, DOMAIN
from .device import AxisNetworkDevice, get_device


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

    hass.data[DOMAIN][device.serial] = device

    await device.async_update_device_registry()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Axis device config entry."""
    device = hass.data[DOMAIN].pop(config_entry.data[CONF_MAC])
    return await device.async_reset()


async def async_populate_options(hass, config_entry):
    """Populate default options for device."""
    device = await get_device(hass, config_entry.data[CONF_DEVICE])

    supported_formats = device.vapix.params.image_format
    camera = bool(supported_formats)

    options = {
        CONF_CAMERA: camera,
        CONF_EVENTS: True,
        CONF_TRIGGER_TIME: DEFAULT_TRIGGER_TIME,
    }

    hass.config_entries.async_update_entry(config_entry, options=options)
