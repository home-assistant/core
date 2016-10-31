"""
Support for GPSLogger platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gpslogger/
"""
import logging

from homeassistant.const import HTTP_UNPROCESSABLE_ENTITY
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']


def setup_scanner(hass, config, see):
    """Setup an endpoint for the GPSLogger application."""
    hass.wsgi.register_view(LocationSet(hass, see))

    return True


class LocationSet(HomeAssistantView):
    """View to handle locative requests."""

    url = '/api/gpslogger'
    name = 'api:gpslogger'

    def __init__(self, hass, see):
        """Initialize Location url endpoints."""
        super().__init__(hass)
        self.see = see

    def get(self, request):
        """Location message received as GET."""
        data = request.values

        if 'latitude' not in data or 'longitude' not in data:
            return ('Latitude and longitude not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'device' not in data:
            _LOGGER.error('Device id not specified.')
            return ('Device id not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        latitude = data['latitude']
        longitude = data['longitude']
        device = data['device']

        _LOGGER.debug('Received message from GPSLogger: %s (%s, %s)', device,
                      latitude, longitude)

        kwargs = {
            'dev_id': data['device'],
            'gps': (float(data['latitude']), float(data['longitude']))
        }

        if 'accuracy' in data:
            kwargs['gps_accuracy'] = int(float(data['accuracy']))
        if 'battery' in data:
            kwargs['battery'] = float(data['battery'])

        self.see(**kwargs)
        return 'Setting location for {}'.format(data['device'])

    # pylint: disable=no-self-use
    def post(self, request):
        """Location message received as POST."""
        _LOGGER.error('Received unidentified POST message from GPSLogger')
        return ('Received unidentified message: POST',
                HTTP_UNPROCESSABLE_ENTITY)
