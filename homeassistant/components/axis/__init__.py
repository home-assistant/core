"""Support for Axis devices."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_LOCATION, CONF_EVENT, CONF_HOST, CONF_INCLUDE, CONF_MAC,
    CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_TRIGGER_TIME, CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util.json import load_json, save_json

from .config_flow import configured_devices, DEVICE_SCHEMA
from .const import DOMAIN
from .device import AxisNetworkDevice

REQUIREMENTS = ['axis==16']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.schema_with_slug_keys(DEVICE_SCHEMA),
}, extra=vol.ALLOW_EXTRA)

SERVICE_VAPIX_CALL = 'vapix_call'
SERVICE_VAPIX_CALL_RESPONSE = 'vapix_call_response'
SERVICE_CGI = 'cgi'
SERVICE_ACTION = 'action'
SERVICE_PARAM = 'param'
SERVICE_DEFAULT_CGI = 'param.cgi'
SERVICE_DEFAULT_ACTION = 'update'

SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(SERVICE_PARAM): cv.string,
    vol.Optional(SERVICE_CGI, default=SERVICE_DEFAULT_CGI): cv.string,
    vol.Optional(SERVICE_ACTION, default=SERVICE_DEFAULT_ACTION): cv.string,
})


async def async_setup(hass, config):
    """Set up for Axis devices."""
    if DOMAIN in config:

        for device_name in config[DOMAIN]:
            device_config = config[DOMAIN][device_name]

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

    device = AxisNetworkDevice(hass, config_entry)
    hass.data[DOMAIN][config_entry.data[CONF_MAC]] = device

    if not await device.async_setup():
        return False

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, device.serial)},
        manufacturer="Axis Communications AB",
        model="{} {}".format(device.model_id, device.product_type),
        name=device.name,
        sw_version=device.fw_version,
    )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    device = hass.data[DOMAIN].pop(config_entry.data[CONF_MAC])
    return await device.async_reset()
