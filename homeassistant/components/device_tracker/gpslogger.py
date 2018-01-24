"""
Support for the GPSLogger platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gpslogger/
"""
import asyncio
from functools import partial
import logging

import voluptuous as vol

from homeassistant.const import HTTP_UNPROCESSABLE_ENTITY
from homeassistant.components.http import HomeAssistantView
# pylint: disable=unused-import
from homeassistant.components.device_tracker import (  # NOQA
    DOMAIN, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
})

def setup_scanner(hass, config, see, discovery_info=None):
    """Set up an endpoint for the GPSLogger application."""
    max_gps_accuracy = config.get(CONF_MAX_GPS_ACCURACY)

    hass.http.register_view(GPSLoggerView(see, max_accuracy=max_gps_accuracy))

    return True


class GPSLoggerView(HomeAssistantView):
    """View to handle GPSLogger requests."""

    url = '/api/gpslogger'
    name = 'api:gpslogger'

    def __init__(self, see, max_accuracy=None):
        """Initialize GPSLogger url endpoints."""
        self.see = see
        self.max_accuracy = max_accuracy

    @asyncio.coroutine
    def get(self, request):
        """Handle for GPSLogger message received as GET."""
        res = yield from self._handle(request.app['hass'], request.query)
        return res

    @asyncio.coroutine
    def _handle(self, hass, data):
        """Handle GPSLogger requests."""
        if 'latitude' not in data or 'longitude' not in data:
            return ('Latitude and longitude not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'device' not in data:
            _LOGGER.error("Device id not specified")
            return ('Device id not specified.', HTTP_UNPROCESSABLE_ENTITY)

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

        if self.max_accuracy is None or accuracy < self.max_accuracy:
          yield from hass.async_add_job(
            partial(self.see, dev_id=device,
                    gps=gps_location, battery=battery,
                    gps_accuracy=accuracy,
                    attributes=attrs))

          return 'Setting location for {}'.format(device)

        return 'Skipping location for {} max_gps_accuracy not met.'.format(device)


