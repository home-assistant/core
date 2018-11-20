"""
Support for Azure Maps travel time sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.azure_maps_travel_time/
"""
from datetime import datetime
from datetime import timedelta
import logging
import requests
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, EVENT_HOMEASSISTANT_START, ATTR_LATITUDE,
    ATTR_LONGITUDE)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import location
import homeassistant.util.dt as dt_util
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

ROUTE_URL = 'https://atlas.microsoft.com/route/directions/json'
CONF_DESTINATION = 'destination'
CONF_OPTIONS = 'options'
CONF_ORIGIN = 'origin'
CONF_TRAVEL_MODE = 'travelMode'

DEFAULT_NAME = 'Azure Maps Travel Time'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

AVOID = ['tollRoads', 'motorways', 'ferries', 'unpavedRoads']
TRAVEL_MODE = ['car', 'pedestrian', 'bicycle']
ROUTE_TYPE = ['eco', 'fastest', 'shortest', 'thrilling']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_OPTIONS, default={CONF_TRAVEL_MODE: 'car'}): vol.All(
        dict, vol.Schema({
            vol.Optional(CONF_TRAVEL_MODE, default='car'): vol.In(TRAVEL_MODE),
            vol.Optional('avoid'): vol.In(AVOID),
            vol.Exclusive('arriveAt', 'time'): cv.string,
            vol.Exclusive('departAt', 'time'): cv.string,
            vol.Optional('RouteType', default='fastest'): vol.In(ROUTE_TYPE),
        }))
})

TRACKABLE_DOMAINS = ['device_tracker', 'sensor', 'zone']
DATA_KEY = 'azure_maps_travel_time'


def convert_time_to_utc(timestr):
    """Take a string like 08:00:00 and convert it to a datetime."""
    combined = datetime.combine(
        dt_util.start_of_local_day(), dt_util.parse_time(timestr))
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return dt_util.as_utc(combined)


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the Azure maps travel time platform."""
    def run_setup(event):
        """Delay the setup until Home Assistant is fully initialized.

        This allows any entities to be created already
        """
        options = config.get(CONF_OPTIONS)

        if DATA_KEY not in hass.data:
            hass.data[DATA_KEY] = []
            hass.services.register(
                DOMAIN, 'azure_maps_travel_sensor_update', update)

        titled_mode = options.get(CONF_TRAVEL_MODE).title()
        formatted_name = "{} - {}".format(DEFAULT_NAME, titled_mode)
        name = config.get(CONF_NAME, formatted_name)
        api_key = config.get(CONF_API_KEY)
        origin = config.get(CONF_ORIGIN)
        destination = config.get(CONF_DESTINATION)

        sensor = AzureMapsTravelTimeSensor(
            hass, name, api_key, origin, destination, options)
        hass.data[DATA_KEY].append(sensor)
        add_entities_callback([sensor])

    def update(service):
        """Update service for manual updates."""
        entity_id = service.data.get('entity_id')
        for sensor in hass.data[DATA_KEY]:
            if sensor.entity_id == entity_id:
                sensor.update(no_throttle=True)
                sensor.schedule_update_ha_state()

    # Wait until start event is sent to load this component.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, run_setup)


class AzureMapsTravelTimeSensor(Entity):
    """Representation of a Azure Maps travel time sensor."""

    def __init__(self, hass, name, api_key, origin, destination, options):
        """Initialize the sensor."""
        self._hass = hass
        self._key = api_key
        self._name = name
        self._options = options
        self._unit_of_measurement = 'min'
        self._state = None
        self._attributes = None
        self.valid_api_connection = True

        # Check if location is a trackable entity
        if origin.split('.', 1)[0] in TRACKABLE_DOMAINS:
            self._origin_entity_id = origin
        else:
            self._origin = origin

        if destination.split('.', 1)[0] in TRACKABLE_DOMAINS:
            self._destination_entity_id = destination
        else:
            self._destination = destination

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Azure Maps."""
        options_copy = dict(self._options.copy())
        dtime = options_copy.get('departAt')
        atime = options_copy.get('arriveAt')
        if dtime is not None and ':' in dtime:
            options_copy['departAt'] = convert_time_to_utc(dtime).isoformat()
        elif dtime is not None:
            options_copy['departAt'] = dtime.isoformat()
        if atime is not None and ':' in atime:
            options_copy['arriveAt'] = convert_time_to_utc(atime).isoformat()
        elif atime is not None:
            options_copy['arriveAt'] = atime.isoformat()

        # Convert device_trackers to friendly locations
        if hasattr(self, '_origin_entity_id'):
            self._origin = self._get_location_from_entity(
                self._origin_entity_id
            )
        if hasattr(self, '_destination_entity_id'):
            self._destination = self._get_location_from_entity(
                self._destination_entity_id
            )

        self._destination = self._resolve_zone(self._destination)
        self._origin = self._resolve_zone(self._origin)

        if self._destination is not None and self._origin is not None:
            _LOGGER.debug(
                'origin: '+self._origin+', destination: '+self._destination)
            options_copy['query'] = self._origin + ":" + self._destination
            options_copy['api-version'] = 1.0
            options_copy['subscription-key'] = self._key
            options_copy['traffic'] = True
            options_copy['ComputeTravelTimeFor'] = 'all'

            resp = requests.get(
                ROUTE_URL,
                params=options_copy
                )
            # pylint: disable=no-member
            if resp.status_code == requests.codes.ok:
                response = resp.json()
                summary = response['routes'][0]['summary']
                summary.update(dict(self._options))
                self._attributes = summary
                self._state = round(summary['travelTimeInSeconds']/60)
            else:
                _LOGGER.error(resp)
                self.valid_api_connection = False
                raise HomeAssistantError

    def _get_location_from_entity(self, entity_id):
        """Get the location from the entity state or attributes."""
        entity = self._hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            self.valid_api_connection = False
            return None

        # Check if the entity has location attributes
        if location.has_location(entity):
            return self._get_location_from_attributes(entity)

        # Check if device is in a zone
        zone_entity = self._hass.states.get("zone.%s" % entity.state)
        if location.has_location(zone_entity):
            _LOGGER.debug(
                "%s is in %s, getting zone location",
                entity_id, zone_entity.entity_id
            )
            return self._get_location_from_attributes(zone_entity)

        # If zone was not found in state then use the state as the location
        if entity_id.startswith("sensor."):
            return entity.state

        # When everything fails just return nothing
        return None

    @staticmethod
    def _get_location_from_attributes(entity):
        """Get the lat/long string from an entities attributes."""
        attr = entity.attributes
        return "%s,%s" % (attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))

    def _resolve_zone(self, friendly_name):
        entities = self._hass.states.all()
        for entity in entities:
            if entity.domain == 'zone' and entity.name == friendly_name:
                return self._get_location_from_attributes(
                    entity).replace(' ', '')

        return friendly_name.replace(' ', '')
