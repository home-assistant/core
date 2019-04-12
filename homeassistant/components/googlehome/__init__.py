"""Support Google Home units."""
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

NAME = 'GoogleHome'

CONF_DEVICE_TYPES = 'device_types'
CONF_RSSI_THRESHOLD = 'rssi_threshold'
CONF_TRACK_ALARMS = 'track_alarms'
CONF_TRACK_DEVICES = 'track_devices'

DEVICE_TYPES = [1, 2, 3]
DEFAULT_RSSI_THRESHOLD = -70

DEVICE_CONFIG = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_DEVICE_TYPES, default=DEVICE_TYPES):
        vol.All(cv.ensure_list, [vol.In(DEVICE_TYPES)]),
    vol.Optional(CONF_RSSI_THRESHOLD, default=DEFAULT_RSSI_THRESHOLD):
        vol.Coerce(int),
    vol.Optional(CONF_TRACK_ALARMS, default=False): cv.boolean,
    vol.Optional(CONF_TRACK_DEVICES, default=True): cv.boolean,
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
        if device[CONF_TRACK_DEVICES]:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, 'device_tracker', DOMAIN, device, config))

        if device[CONF_TRACK_ALARMS]:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, 'sensor', DOMAIN, device, config))

    return True


class GoogleHomeClient:
    """Handle all communication with the Google Home unit."""

    def __init__(self, hass):
        """Initialize the Google Home Client."""
        self.hass = hass
        self._connected = None

    async def update_info(self, host):
        """Update data from Google Home."""
        from googledevices.api.connect import Cast
        _LOGGER.debug("Updating Google Home info for %s", host)
        session = async_get_clientsession(self.hass)

        device_info = await Cast(host, self.hass.loop, session).info()
        device_info_data = await device_info.get_device_info()
        self._connected = bool(device_info_data)

        self.hass.data[DOMAIN][host]['info'] = device_info_data

    async def update_bluetooth(self, host):
        """Update bluetooth from Google Home."""
        from googledevices.api.connect import Cast
        _LOGGER.debug("Updating Google Home bluetooth for %s", host)
        session = async_get_clientsession(self.hass)

        bluetooth = await Cast(host, self.hass.loop, session).bluetooth()
        await bluetooth.scan_for_devices()
        await asyncio.sleep(5)
        bluetooth_data = await bluetooth.get_scan_result()

        self.hass.data[DOMAIN][host]['bluetooth'] = bluetooth_data

    async def update_alarms(self, host):
        """Update alarms from Google Home."""
        from googledevices.api.connect import Cast
        _LOGGER.debug("Updating Google Home bluetooth for %s", host)
        session = async_get_clientsession(self.hass)

        assistant = await Cast(host, self.hass.loop, session).assistant()
        alarms_data = await assistant.get_alarms()

        self.hass.data[DOMAIN][host]['alarms'] = alarms_data
