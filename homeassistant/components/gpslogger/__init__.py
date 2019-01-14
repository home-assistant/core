"""
Support for GPSLogger.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/gpslogger/
"""
import logging
from hmac import compare_digest

import voluptuous as vol
from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp.web_request import Request

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView, CONF_API_PASSWORD
from homeassistant.const import CONF_PASSWORD, HTTP_UNPROCESSABLE_ENTITY
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'gpslogger'
DEPENDENCIES = ['http']

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Optional(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

URL = '/api/{}'.format(DOMAIN)

TRACKER_UPDATE = '{}_tracker_update'.format(DOMAIN)


async def async_setup(hass, hass_config):
    """Set up the GPSLogger component."""
    config = hass_config[DOMAIN]
    hass.http.register_view(GPSLoggerView(config))

    hass.async_create_task(
        async_load_platform(hass, 'device_tracker', DOMAIN, {}, hass_config)
    )
    return True


class GPSLoggerView(HomeAssistantView):
    """View to handle GPSLogger requests."""

    url = URL
    name = 'api:gpslogger'

    def __init__(self, config):
        """Initialize GPSLogger url endpoints."""
        self._password = config.get(CONF_PASSWORD)
        # this component does not require external authentication if
        # password is set
        self.requires_auth = self._password is None

    async def get(self, request: Request):
        """Handle for GPSLogger message received as GET."""
        hass = request.app['hass']
        data = request.query

        if self._password is not None:
            authenticated = CONF_API_PASSWORD in data and compare_digest(
                self._password,
                data[CONF_API_PASSWORD]
            )
            if not authenticated:
                raise HTTPUnauthorized()

        if 'latitude' not in data or 'longitude' not in data:
            return ('Latitude and longitude not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'device' not in data:
            _LOGGER.error("Device id not specified")
            return ('Device id not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        device = data['device'].replace('-', '')
        gps_location = (data['latitude'], data['longitude'])
        accuracy = 200
        battery = -1

        if 'accuracy' in data:
            accuracy = int(float(data['accuracy']))
        if 'battery' in data:
            battery = float(data['battery'])

        attrs = {}
        if 'speed' in data:
            attrs['speed'] = float(data['speed'])
        if 'direction' in data:
            attrs['direction'] = float(data['direction'])
        if 'altitude' in data:
            attrs['altitude'] = float(data['altitude'])
        if 'provider' in data:
            attrs['provider'] = data['provider']
        if 'activity' in data:
            attrs['activity'] = data['activity']

        async_dispatcher_send(
            hass,
            TRACKER_UPDATE,
            device,
            gps_location,
            battery,
            accuracy,
            attrs
        )

        return 'Setting location for {}'.format(device)
