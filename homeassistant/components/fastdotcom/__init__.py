"""
Support for testing internet speed via Fast.com.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fastdotcom/
"""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_change

REQUIREMENTS = ['fastdotcom==0.0.3']

DOMAIN = 'fastdotcom'
DATA_UPDATED = '{}_data_updated'.format(DOMAIN)

_LOGGER = logging.getLogger(__name__)

CONF_SECOND = 'second'
CONF_MINUTE = 'minute'
CONF_HOUR = 'hour'
CONF_MANUAL = 'manual'

# pylint: disable=invalid-name
minutes_or_seconds = vol.All(vol.Coerce(int), vol.Range(0, 59))
hours = vol.All(vol.Coerce(int), vol.Range(0, 23))
# pylint: enable=invalid-name


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_SECOND, default=[0]):
            vol.All(cv.ensure_list, [minutes_or_seconds]),
        vol.Optional(CONF_MINUTE, default=[0]):
            vol.All(cv.ensure_list, [minutes_or_seconds]),
        vol.Optional(CONF_HOUR):
            vol.All(cv.ensure_list, [hours]),
        vol.Optional(CONF_MANUAL, default=False): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Fast.com component."""
    conf = config[DOMAIN]
    data = hass.data[DOMAIN] = SpeedtestData(hass, conf)

    def update(call=None):
        """Service call to manually update the data."""
        data.update()

    hass.services.register(DOMAIN, 'speedtest', update)

    hass.async_create_task(
        async_load_platform(hass, 'sensor', DOMAIN, {}, config)
    )

    return True


class SpeedtestData:
    """Get the latest data from fast.com."""

    def __init__(self, hass, config):
        """Initialize the data object."""
        self.data = None
        self._hass = hass
        if not config.get(CONF_MANUAL):
            track_time_change(
                hass, self.update, second=config.get(CONF_SECOND),
                minute=config.get(CONF_MINUTE), hour=config.get(CONF_HOUR))

    def update(self):
        """Get the latest data from fast.com."""
        from fastdotcom import fast_com
        _LOGGER.info("Executing fast.com speedtest")
        self.data = {'download': fast_com()}
        dispatcher_send(self._hass, DATA_UPDATED)
