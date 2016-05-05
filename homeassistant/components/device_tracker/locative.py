"""
Support for the Locative platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.locative/
"""
import logging
from functools import partial

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import HTTP_UNPROCESSABLE_ENTITY, STATE_NOT_HOME

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

URL_API_LOCATIVE_ENDPOINT = "/api/locative"


def setup_scanner(hass, config, see):
    """Setup an endpoint for the Locative application."""
    # POST would be semantically better, but that currently does not work
    # since Locative sends the data as key1=value1&key2=value2
    # in the request body, while Home Assistant expects json there.
    hass.http.register_path(
        'GET', URL_API_LOCATIVE_ENDPOINT,
        partial(_handle_get_api_locative, hass, see))

    return True


def _handle_get_api_locative(hass, see, handler, path_match, data):
    """Locative message received."""
    if not _check_data(handler, data):
        return

    device = data['device'].replace('-', '')
    location_name = data['id'].lower()
    direction = data['trigger']

    if direction == 'enter':
        see(dev_id=device, location_name=location_name)
        handler.write_text("Setting location to {}".format(location_name))

    elif direction == 'exit':
        current_state = hass.states.get("{}.{}".format(DOMAIN, device))

        if current_state is None or current_state.state == location_name:
            see(dev_id=device, location_name=STATE_NOT_HOME)
            handler.write_text("Setting location to not home")
        else:
            # Ignore the message if it is telling us to exit a zone that we
            # aren't currently in. This occurs when a zone is entered before
            # the previous zone was exited. The enter message will be sent
            # first, then the exit message will be sent second.
            handler.write_text(
                'Ignoring exit from {} (already in {})'.format(
                    location_name, current_state))

    elif direction == 'test':
        # In the app, a test message can be sent. Just return something to
        # the user to let them know that it works.
        handler.write_text("Received test message.")

    else:
        handler.write_text(
            "Received unidentified message: {}".format(direction),
            HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Received unidentified message from Locative: %s",
                      direction)


def _check_data(handler, data):
    """Check the data."""
    if 'latitude' not in data or 'longitude' not in data:
        handler.write_text("Latitude and longitude not specified.",
                           HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Latitude and longitude not specified.")
        return False

    if 'device' not in data:
        handler.write_text("Device id not specified.",
                           HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Device id not specified.")
        return False

    if 'id' not in data:
        handler.write_text("Location id not specified.",
                           HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Location id not specified.")
        return False

    if 'trigger' not in data:
        handler.write_text("Trigger is not specified.",
                           HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Trigger is not specified.")
        return False

    return True
