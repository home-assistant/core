"""
homeassistant.components.device_tracker.locative
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Locative platform for the device tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.locative/
"""
import logging
from functools import partial

from homeassistant.const import (
    HTTP_UNPROCESSABLE_ENTITY, HTTP_INTERNAL_SERVER_ERROR, STATE_NOT_HOME)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http', 'zone']

URL_API_LOCATIVE_ENDPOINT = "/api/locative"


def setup_scanner(hass, config, see):
    """ Set up an endpoint for the Locative app. """

    # POST would be semantically better, but that currently does not work
    # since Locative sends the data as key1=value1&key2=value2
    # in the request body, while Home Assistant expects json there.

    hass.http.register_path(
        'GET', URL_API_LOCATIVE_ENDPOINT,
        partial(_handle_get_api_locative, hass, see))

    return True


def _handle_get_api_locative(hass, see, handler, path_match, data):
    """ Locative message received. """

    if not _check_data(handler, data):
        return

    device = data['device'].replace('-', '')
    location_name = data['id']
    direction = data['trigger']

    try:
        gps_coords = (float(data['latitude']), float(data['longitude']))
    except ValueError:
        handler.write_json_message("Invalid latitude / longitude format.",
                                   HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Received invalid latitude / longitude format.")
        return

    if direction == 'enter':
        zones = [state for state in hass.states.entity_ids('zone')]
        _LOGGER.info(zones)

        if "zone.{}".format(location_name.lower()) in zones:
            see(dev_id=device, location_name=location_name)
            handler.write_json_message(
                "Set new location to {}".format(location_name))
        else:
            see(dev_id=device, gps=gps_coords)
            handler.write_json_message(
                "Set new location to {}".format(gps_coords))

    elif direction == 'exit':
        current_zone = hass.states.get(
            "{}.{}".format("device_tracker", device)).state

        if current_zone.lower() == location_name.lower():
            see(dev_id=device, location_name=STATE_NOT_HOME)
            handler.write_json_message("Set new location to not home")
        else:
            # Ignore the message if it is telling us to exit a zone that we
            # aren't currently in. This occurs when a zone is entered before
            # the previous zone was exited. The enter message will be sent
            # first, then the exit message will be sent second.
            handler.write_json_message(
                "Ignoring transition to {}".format(location_name))

    else:
        handler.write_json_message(
            "Received unidentified message: {}".format(direction))
        _LOGGER.error("Received unidentified message from Locative: %s",
                      direction)


def _check_data(handler, data):
    if not isinstance(data, dict):
        handler.write_json_message("Error while parsing Locative message.",
                                   HTTP_INTERNAL_SERVER_ERROR)
        _LOGGER.error("Error while parsing Locative message: "
                      "data is not a dict.")
        return False

    if 'latitude' not in data or 'longitude' not in data:
        handler.write_json_message("Latitude and longitude not specified.",
                                   HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Latitude and longitude not specified.")
        return False

    if 'device' not in data:
        handler.write_json_message("Device id not specified.",
                                   HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Device id not specified.")
        return False

    if 'id' not in data:
        handler.write_json_message("Location id not specified.",
                                   HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Location id not specified.")
        return False

    if 'trigger' not in data:
        handler.write_json_message("Trigger is not specified.",
                                   HTTP_UNPROCESSABLE_ENTITY)
        _LOGGER.error("Trigger is not specified.")
        return False

    return True
