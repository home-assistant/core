"""
Support for the GPSLogger platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gpslogger/
"""
import logging
from hmac import compare_digest

from aiohttp.web import Request, HTTPUnauthorized  # NOQA
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PASSWORD, HTTP_UNPROCESSABLE_ENTITY
)
from homeassistant.components.http import (
    CONF_API_PASSWORD, HomeAssistantView
)
# pylint: disable=unused-import
from homeassistant.components.device_tracker import (  # NOQA
    DOMAIN, PLATFORM_SCHEMA
)
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PASSWORD): cv.string,
})


async def async_setup_scanner(hass: HomeAssistantType, config: ConfigType,
                              async_see, discovery_info=None):
    """Set up an endpoint for the GPSLogger application."""
    hass.http.register_view(GPSLoggerView(async_see, config))

    return True


class GPSLoggerView(HomeAssistantView):
    """View to handle GPSLogger requests."""

    url = '/api/gpslogger'
    name = 'api:gpslogger'

    def __init__(self, async_see, config):
        """Initialize GPSLogger url endpoints."""
        self.async_see = async_see
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

        hass.async_add_job(self.async_see(
            dev_id=device,
            gps=gps_location, battery=battery,
            gps_accuracy=accuracy,
            attributes=attrs
        ))

        return 'Setting location for {}'.format(device)
