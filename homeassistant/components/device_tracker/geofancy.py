"""
homeassistant.components.device_tracker.geofancy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Geofancy platform for the device tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.geofancy/
"""
from homeassistant.const import (
    HTTP_UNPROCESSABLE_ENTITY, HTTP_INTERNAL_SERVER_ERROR)
from homeassistant.const import (ATTR_LATITUDE, ATTR_LONGITUDE)

DEPENDENCIES = ['http', 'zone']

_SEE = 0
_HASS = None

URL_API_GEOFANCY_ENDPOINT = "/api/geofancy"


def setup_scanner(hass, config, see):
    """ Set up an endpoint for the Geofancy app. """

    # Use a global variable to keep setup_scanner compact when using a callback
    global _SEE
    _SEE = see

    global _HASS
    _HASS = hass

    # POST would be semantically better, but that currently does not work
    # since Geofancy sends the data as key1=value1&key2=value2
    # in the request body, while Home Assistant expects json there.

    hass.http.register_path(
        'GET', URL_API_GEOFANCY_ENDPOINT, _handle_get_api_geofancy)

    return True


def available_zones():
    """ Returns a string with available zone names. """
    return ", ".join(_HASS.states.entity_ids('zone')).replace("zone.", "")


def _handle_get_api_geofancy(handler, path_match, data):
    """ Geofancy message received. """

    if not isinstance(data, dict):
        handler.write_json_message(
            "Error while parsing Geofancy message.",
            HTTP_INTERNAL_SERVER_ERROR)
        return
    if ('latitude' not in data or 'longitude' not in data) and \
            'zone' not in data and 'away' not in data:
        handler.write_json_message(
            "Location not specified. Either use the latitude & longtitude, "
            "the zone or the away parameter.", HTTP_UNPROCESSABLE_ENTITY)
        return
    if 'device' not in data:
        handler.write_json_message(
            "Please specify the device parameter.",
            HTTP_UNPROCESSABLE_ENTITY)
        return

    if 'id' not in data and ('latitude' in data or 'longitude' in data):
        handler.write_json_message(
            "Please specify the id parameter to set the location name.",
            HTTP_UNPROCESSABLE_ENTITY)
        return

    # entity id's in Home Assistant must be alphanumerical
    device_uuid = data['device']
    device_entity_id = device_uuid.replace('-', '')

    gps_coords = None
    location_name = None
    if 'zone' in data:
        zone_id = "zone." + data['zone']
        zone = _HASS.states.get(zone_id)
        if zone is None:
            handler.write_json_message(
                "The zone you specified is invalid. Available zones: %s" %
                available_zones(), HTTP_UNPROCESSABLE_ENTITY)
            return
        gps_coords = (zone.attributes[ATTR_LATITUDE],
                      zone.attributes[ATTR_LONGITUDE])
        message = "Set %s's location to zone %s." % (device_uuid, zone.name)
    elif 'away' in data:
        gps_coords = None
        message = "Set %s's location to away." % device_uuid
    else:
        try:
            gps_coords = (float(data['latitude']), float(data['longitude']))
            location_name = data['id']
            message = "Set %s's location to %f / %f (%s)."\
                % (device_uuid, gps_coords[0], gps_coords[1], location_name)
        except ValueError:
            # If invalid latitude / longitude format
            handler.write_json_message(
                "Invalid latitude / longitude format.",
                HTTP_UNPROCESSABLE_ENTITY)
            return

    _SEE(dev_id=device_entity_id, gps=gps_coords, location_name=location_name)

    handler.write_json_message(message)
