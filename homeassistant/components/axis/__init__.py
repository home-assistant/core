"""Support for Axis devices."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_LOCATION, CONF_DEVICE, CONF_EVENT, CONF_HOST, CONF_INCLUDE, CONF_MAC,
    CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_TRIGGER_TIME, CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util.json import load_json, save_json

from .config_flow import configured_devices, DEVICE_SCHEMA
from .const import CONF_CAMERA, CONF_EVENTS, DEFAULT_TRIGGER_TIME, DOMAIN
from .device import AxisNetworkDevice, get_device

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

    if not config_entry.options:
        await async_populate_options(hass, config_entry)

    if not await device.async_setup():
        return False

    hass.data[DOMAIN][config_entry.data[CONF_MAC]] = device

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)

    return True


async def async_populate_options(hass, config_entry):
    """"""
    from axis.event import device_events
    from axis.vapix import VAPIX_IMAGE_FORMAT

    device = await get_device(hass, config_entry.data[CONF_DEVICE])
    supported_events = await hass.async_add_executor_job(
        device_events, device.config)

    video_motion = ['vmd4', 'vmd3', 'motion']

    events = set(supported_events.keys())

    for event in video_motion[1:]:
        if event in events and len(set(video_motion).intersection(events)) > 1:
            events.remove(event)

    supported_formats = device.vapix.get_param(VAPIX_IMAGE_FORMAT)

    camera = True if supported_formats else False

    options = {
        CONF_CAMERA: camera,
        CONF_EVENTS: sorted(list(events)),
        CONF_TRIGGER_TIME: DEFAULT_TRIGGER_TIME
    }

    hass.config_entries.async_update_entry(config_entry, options=options)
