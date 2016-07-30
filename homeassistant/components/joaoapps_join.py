"""
Component for Joaoapps Join services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/join/
"""
import logging
import voluptuous as vol
from homeassistant.const import CONF_NAME, CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/nkgilley/python-join-api/archive/'
    '3e1e849f1af0b4080f551b62270c6d244d5fbcbd.zip#python-join-api==0.0.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'joaoapps_join'
CONF_DEVICE_ID = 'device_id'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [{
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_API_KEY): cv.string
    }])
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=too-many-locals
def register_device(hass, device_id, api_key, name):
    """Method to register services for each join device listed."""
    from pyjoin import (ring_device, set_wallpaper, send_sms,
                        send_file, send_url, send_notification)

    def ring_service(service):
        """Service to ring devices."""
        ring_device(device_id, api_key=api_key)

    def set_wallpaper_service(service):
        """Service to set wallpaper on devices."""
        set_wallpaper(device_id, url=service.data.get('url'), api_key=api_key)

    def send_file_service(service):
        """Service to send files to devices."""
        send_file(device_id, url=service.data.get('url'), api_key=api_key)

    def send_url_service(service):
        """Service to open url on devices."""
        send_url(device_id, url=service.data.get('url'), api_key=api_key)

    def send_tasker_service(service):
        """Service to open url on devices."""
        send_notification(device_id=device_id,
                          text=service.data.get('command'),
                          api_key=api_key)

    def send_sms_service(service):
        """Service to send sms from devices."""
        send_sms(device_id=device_id,
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
    """Setup Join services."""
    from pyjoin import get_devices
    for device in config[DOMAIN]:
        device_id = device.get(CONF_DEVICE_ID)
        api_key = device.get(CONF_API_KEY)
        name = device.get(CONF_NAME)
        name = name.lower().replace(" ", "_") + "_" if name else ""
        if api_key:
            if not get_devices(api_key):
                _LOGGER.error("Error connecting to Join, check API key")
                return False
        register_device(hass, device_id, api_key, name)
    return True
