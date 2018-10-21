"""
Support for the Locative platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.locative/
"""
from functools import partial
import logging

from homeassistant.const import (
    ATTR_LATITUDE, ATTR_LONGITUDE, STATE_NOT_HOME, HTTP_UNPROCESSABLE_ENTITY)
from homeassistant.components.http import HomeAssistantView
# pylint: disable=unused-import
from homeassistant.components.device_tracker import (  # NOQA
    DOMAIN, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']
URL = '/api/locative'


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up an endpoint for the Locative application."""
    hass.http.register_view(LocativeView(see))

    return True


class LocativeView(HomeAssistantView):
    """View to handle Locative requests."""

    url = URL
    name = 'api:locative'

    def __init__(self, see):
        """Initialize Locative URL endpoints."""
        self.see = see

    async def get(self, request):
        """Locative message received as GET."""
        res = await self._handle(request.app['hass'], request.query)
        return res

    async def post(self, request):
        """Locative message received."""
        data = await request.post()
        res = await self._handle(request.app['hass'], data)
        return res

    async def _handle(self, hass, data):
        """Handle locative request."""
        if 'latitude' not in data or 'longitude' not in data:
            return ('Latitude and longitude not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'device' not in data:
            _LOGGER.error('Device id not specified.')
            return ('Device id not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'trigger' not in data:
            _LOGGER.error('Trigger is not specified.')
            return ('Trigger is not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'id' not in data and data['trigger'] != 'test':
            _LOGGER.error('Location id not specified.')
            return ('Location id not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        device = data['device'].replace('-', '')
        location_name = data.get('id', data['trigger']).lower()
        direction = data['trigger']
        gps_location = (data[ATTR_LATITUDE], data[ATTR_LONGITUDE])

        if direction == 'enter':
            await hass.async_add_job(
                partial(self.see, dev_id=device, location_name=location_name,
                        gps=gps_location))
            return 'Setting location to {}'.format(location_name)

        if direction == 'exit':
            current_state = hass.states.get(
                '{}.{}'.format(DOMAIN, device))

            if current_state is None or current_state.state == location_name:
                location_name = STATE_NOT_HOME
                await hass.async_add_job(
                    partial(self.see, dev_id=device,
                            location_name=location_name, gps=gps_location))
                return 'Setting location to not home'

            # Ignore the message if it is telling us to exit a zone that we
            # aren't currently in. This occurs when a zone is entered
            # before the previous zone was exited. The enter message will
            # be sent first, then the exit message will be sent second.
            return 'Ignoring exit from {} (already in {})'.format(
                location_name, current_state)

        if direction == 'test':
            # In the app, a test message can be sent. Just return something to
            # the user to let them know that it works.
            return 'Received test message.'

        _LOGGER.error('Received unidentified message from Locative: %s',
                      direction)
        return ('Received unidentified message: {}'.format(direction),
                HTTP_UNPROCESSABLE_ENTITY)
