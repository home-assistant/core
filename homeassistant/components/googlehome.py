"""
Support Google Home units.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/googlehome/
"""
import logging

import asyncio
import voluptuous as vol
from homeassistant.const import CONF_DEVICES, CONF_HOST
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['googledevices==1.0.2']

DOMAIN = 'googlehome'
CLIENT = 'googlehome_client'

NAME = DOMAIN

CONF_DEVICE_TYPES = 'device_types'
CONF_RSSI_THRESHOLD = 'rssi_threshold'

DEVICE_TYPES = [1, 2, 3]
DEFAULT_RSSI_THRESHOLD = -70

DEVICE_CONFIG = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_DEVICE_TYPES,
                 default=DEVICE_TYPES): vol.All(cv.ensure_list,
                                                [vol.In(DEVICE_TYPES)]),
    vol.Optional(CONF_RSSI_THRESHOLD,
                 default=DEFAULT_RSSI_THRESHOLD): vol.Coerce(int),
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_CONFIG]),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Google Home component."""
    hass.data[DOMAIN] = {}
    hass.data[CLIENT] = GoogleHomeClient(hass)

    for device in config[DOMAIN][CONF_DEVICES]:
        hass.data[DOMAIN][device['host']] = {}
        discovery.load_platform(hass, 'device_tracker', DOMAIN, device, config)

    return True


class GoogleHomeClient:
    """Handle all communication with the Google Home unit."""

    def __init__(self, hass):
        """Initialize the Google Home Client."""
        self.hass = hass
        self._connected = None

    async def update_data(self, host):
        """Update data from Google Home."""
        from googledevices.api.connect import Cast
        _LOGGER.debug("Updating Google Home data for %s", host)
        session = async_get_clientsession(self.hass)

        device_info = await Cast(host, self.hass.loop, session).info()
        device_info_data = await device_info.get_device_info()
        self._connected = bool(device_info_data)

        bluetooth = await Cast(host, self.hass.loop, session).bluetooth()
        await bluetooth.scan_for_devices()
        await asyncio.sleep(5)
        bluetooth_data = await bluetooth.get_scan_result()

        self.hass.data[DOMAIN][host]['info'] = device_info_data
        self.hass.data[DOMAIN][host]['bluetooth'] = bluetooth_data
