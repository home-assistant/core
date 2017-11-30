"""
Component for Joaoapps Join services.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/join/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_API_KEY

REQUIREMENTS = ['python-join-api==0.0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'joaoapps_join'
CONF_DEVICE_ID = 'device_id'
CONF_DEVICE_IDS = 'device_ids'
CONF_DEVICE_NAMES = 'device_names'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [{
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_DEVICE_IDS): cv.string,
        vol.Optional(CONF_DEVICE_NAMES): cv.string,
        vol.Optional(CONF_NAME): cv.string
    }])
}, extra=vol.ALLOW_EXTRA)


def register_device(hass, api_key, name, device_id, device_ids, device_names):
    """Register services for each join device listed."""
    from pyjoin import (ring_device, set_wallpaper, send_sms,
                        send_file, send_url, send_notification)

    def ring_service(service):
        """Service to ring devices."""
        ring_device(api_key=api_key, device_id=device_id,
                    device_ids=device_ids, device_names=device_names)

    def set_wallpaper_service(service):
        """Service to set wallpaper on devices."""
        set_wallpaper(api_key=api_key, device_id=device_id,
                      device_ids=device_ids, device_names=device_names,
                      url=service.data.get('url'))

    def send_file_service(service):
        """Service to send files to devices."""
        send_file(api_key=api_key, device_id=device_id,
                  device_ids=device_ids, device_names=device_names,
                  url=service.data.get('url'))

    def send_url_service(service):
        """Service to open url on devices."""
        send_url(api_key=api_key, device_id=device_id,
                 device_ids=device_ids, device_names=device_names,
                 url=service.data.get('url'))

    def send_tasker_service(service):
        """Service to open url on devices."""
        send_notification(api_key=api_key, device_id=device_id,
                          device_ids=device_ids, device_names=device_names,
                          text=service.data.get('command'))

    def send_sms_service(service):
        """Service to send sms from devices."""
        send_sms(device_id=device_id,
                 device_ids=device_ids,
                 device_names=device_names,
                 sms_number=service.data.get('number'),
                 sms_text=service.data.get('message'),
                 api_key=api_key)

    hass.services.register(DOMAIN, name + 'ring', ring_service)
    hass.services.register(DOMAIN, name + 'set_wallpaper',
                           set_wallpaper_service)
    hass.services.register(DOMAIN, name + 'send_sms', send_sms_service)
    hass.services.register(DOMAIN, name + 'send_file', send_file_service)
    hass.services.register(DOMAIN, name + 'send_url', send_url_service)
    hass.services.register(DOMAIN, name + 'send_tasker', send_tasker_service)


def setup(hass, config):
    """Set up the Join services."""
    from pyjoin import get_devices
    for device in config[DOMAIN]:
        api_key = device.get(CONF_API_KEY)
        device_id = device.get(CONF_DEVICE_ID)
        device_ids = device.get(CONF_DEVICE_IDS)
        device_names = device.get(CONF_DEVICE_NAMES)
        name = device.get(CONF_NAME)
        name = name.lower().replace(" ", "_") + "_" if name else ""
        if api_key:
            if not get_devices(api_key):
                _LOGGER.error("Error connecting to Join, check API key")
                return False
        if device_id is None and device_ids is None and device_names is None:
            _LOGGER.error("No device was provided. Please specify device_id"
                          ", device_ids, or device_names")
            return False

        register_device(hass, api_key, name,
                        device_id, device_ids, device_names)
    return True
