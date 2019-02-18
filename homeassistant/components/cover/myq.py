"""
Support for MyQ-Enabled Garage Doors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.myq/
"""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA, SUPPORT_CLOSE, SUPPORT_OPEN, CoverDevice)
from homeassistant.const import (
    CONF_PASSWORD, CONF_TYPE, CONF_USERNAME, STATE_CLOSED, STATE_CLOSING,
    STATE_OPEN, STATE_OPENING)
from homeassistant.helpers import aiohttp_client, config_validation as cv

REQUIREMENTS = ['pymyq==1.1.0']
_LOGGER = logging.getLogger(__name__)

MYQ_TO_HASS = {
    'closed': STATE_CLOSED,
    'closing': STATE_CLOSING,
    'open': STATE_OPEN,
    'opening': STATE_OPENING
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TYPE): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the platform."""
    from pymyq import login
    from pymyq.errors import MyQError, UnsupportedBrandError

    websession = aiohttp_client.async_get_clientsession(hass)

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    brand = config[CONF_TYPE]

    try:
        myq = await login(username, password, brand, websession)
    except UnsupportedBrandError:
        _LOGGER.error('Unsupported brand: %s', brand)
        return
    except MyQError as err:
        _LOGGER.error('There was an error while logging in: %s', err)
        return

    devices = await myq.get_devices()
    async_add_entities([MyQDevice(device) for device in devices], True)


class MyQDevice(CoverDevice):
    """Representation of a MyQ cover."""

    def __init__(self, device):
        """Initialize with API object, device id."""
        self._device = device

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return 'garage'

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._device.name

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_OPENING

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return self._device.device_id

    async def async_close_cover(self, **kwargs):
        """Issue close command to cover."""
        await self._device.close()

    async def async_open_cover(self, **kwargs):
        """Issue open command to cover."""
        await self._device.open()

    async def async_update(self):
        """Update status of cover."""
        await self._device.update()
