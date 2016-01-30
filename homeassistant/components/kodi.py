"""
components.kodi
~~~~~~~~~~~~~~~~~~
Component that handles communication with a Kodi media player device.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/kodi/
"""
import logging

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import extract_domain_configs
from homeassistant.util import get_random_string

DOMAIN = "kodi"
REQUIREMENTS = ['jsonrpc-requests==0.1']
_LOGGER = logging.getLogger(__name__)
_KODI_DEVICES = dict()


def setup(hass, config):
    """ Setup the Kodi component. """

    for config_key in extract_domain_configs(config, DOMAIN):
        add_kodi_device(config[config_key])

    return True


def add_kodi_device(config):
    """ Add a single kodi device from a config """
    name = config.get('name', 'kodi_' + get_random_string())

    dev = KodiDevice(
        name,
        config.get('url'),
        auth=(
            config.get('user', ''),
            config.get('password', '')))

    _KODI_DEVICES[name.lower()] = dev

    return dev


def get_kodi_device(name):
    """ Get a Kodi device by name """
    if name not in _KODI_DEVICES:
        raise HomeAssistantError('Referenced Kodi device does not exist')

    return _KODI_DEVICES[name]


def get_kodi_devices():
    """ Get all Kodi devices"""
    for name, dev in _KODI_DEVICES.items():
        yield (name, dev)


class KodiDevice(object):
    """ Represents a XBMC/Kodi device. """

    def __init__(self, name, url, auth=None):
        import jsonrpc_requests
        self._name = name
        self._url = url
        self._api = jsonrpc_requests.Server(url, auth=auth)

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def api(self):
        """ Returns the JSON-RPC proxy object """
        return self._api
