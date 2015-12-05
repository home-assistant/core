"""
homeassistant.components.device_tracker.geofancy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Geofancy platform for the device tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.geofancy/
"""
from homeassistant.const import (
    HTTP_UNPROCESSABLE_ENTITY, HTTP_INTERNAL_SERVER_ERROR)

DEPENDENCIES = ['http']

_SEE = 0

URL_API_GEOFANCY_ENDPOINT = "/api/geofancy"


def setup_scanner(hass, config, see):
    """ Set up an endpoint for the Geofancy app. """

    # Use a global variable to keep setup_scanner compact when using a callback
    global _SEE
    _SEE = see

    # POST would be semantically better, but that currently does not work
    # since Geofancy sends the data as key1=value1&key2=value2
    # in the request body, while Home Assistant expects json there.

    hass.http.register_path(
        'GET', URL_API_GEOFANCY_ENDPOINT, _handle_get_api_geofancy)

    return True


def _handle_get_api_geofancy(handler, path_match, data):
    """ Geofancy message received. """

    if not isinstance(data, dict):
        handler.write_json_message(
            "Error while parsing Geofancy message.",
            HTTP_INTERNAL_SERVER_ERROR)
        return
    if 'latitude' not in data or 'longitude' not in data:
        handler.write_json_message(
            "Location not specified.",
            HTTP_UNPROCESSABLE_ENTITY)
        return
    if 'device' not in data or 'id' not in data:
        handler.write_json_message(
            "Device id or location id not specified.",
            HTTP_UNPROCESSABLE_ENTITY)
        return

    try:
        gps_coords = (float(data['latitude']), float(data['longitude']))
    except ValueError:
        # If invalid latitude / longitude format
        handler.write_json_message(
            "Invalid latitude / longitude format.",
            HTTP_UNPROCESSABLE_ENTITY)
        return

    # entity id's in Home Assistant must be alphanumerical
    device_uuid = data['device']
    device_entity_id = device_uuid.replace('-', '')

    _SEE(dev_id=device_entity_id, gps=gps_coords, location_name=data['id'])

    handler.write_json_message("Geofancy message processed")
