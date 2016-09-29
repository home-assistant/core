"""
Support for the Locative platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.locative/
"""
import logging

from homeassistant.const import HTTP_UNPROCESSABLE_ENTITY, STATE_NOT_HOME
from homeassistant.components.http import HomeAssistantView
# pylint: disable=unused-import
from homeassistant.components.device_tracker import (  # NOQA
    DOMAIN, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']


def setup_scanner(hass, config, see):
    """Setup an endpoint for the Locative application."""
    hass.wsgi.register_view(LocativeView(hass, see))

    return True


class LocativeView(HomeAssistantView):
    """View to handle locative requests."""

    url = '/api/locative'
    name = 'api:locative'

    def __init__(self, hass, see):
        """Initialize Locative url endpoints."""
        super().__init__(hass)
        self.see = see

    def get(self, request):
        """Locative message received as GET."""
        return self.post(request)

    def post(self, request):
        """Locative message received."""
        # pylint: disable=too-many-return-statements
        data = request.values

        if 'latitude' not in data or 'longitude' not in data:
            return ('Latitude and longitude not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'device' not in data:
            _LOGGER.error('Device id not specified.')
            return ('Device id not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'id' not in data:
            _LOGGER.error('Location id not specified.')
            return ('Location id not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        if 'trigger' not in data:
            _LOGGER.error('Trigger is not specified.')
            return ('Trigger is not specified.',
                    HTTP_UNPROCESSABLE_ENTITY)

        device = data['device'].replace('-', '')
        location_name = data['id'].lower()
        direction = data['trigger']

        if direction == 'enter':
            self.see(dev_id=device, location_name=location_name)
            return 'Setting location to {}'.format(location_name)

        elif direction == 'exit':
            current_state = self.hass.states.get(
                '{}.{}'.format(DOMAIN, device))

            if current_state is None or current_state.state == location_name:
                self.see(dev_id=device, location_name=STATE_NOT_HOME)
                return 'Setting location to not home'
            else:
                # Ignore the message if it is telling us to exit a zone that we
                # aren't currently in. This occurs when a zone is entered
                # before the previous zone was exited. The enter message will
                # be sent first, then the exit message will be sent second.
                return 'Ignoring exit from {} (already in {})'.format(
                    location_name, current_state)

        elif direction == 'test':
            # In the app, a test message can be sent. Just return something to
            # the user to let them know that it works.
            return 'Received test message.'

        else:
            _LOGGER.error('Received unidentified message from Locative: %s',
                          direction)
            return ('Received unidentified message: {}'.format(direction),
                    HTTP_UNPROCESSABLE_ENTITY)
