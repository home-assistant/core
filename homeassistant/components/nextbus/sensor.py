"""NextBus sensor."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utc_from_timestamp

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'nextbus'

CONF_AGENCY = 'agency'
CONF_ROUTE = 'route'
CONF_STOP = 'stop'

ICON = 'mdi:bus'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_AGENCY): cv.string,
    vol.Required(CONF_ROUTE): cv.string,
    vol.Required(CONF_STOP): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


def validate_value(value_name, value, value_list):
    """Validate tag value is in the list of items and logs error if not."""
    valid_values = {
        v['tag']: v['title']
        for v in value_list
    }
    if value not in valid_values:
        _LOGGER.error(
            'Invalid %s tag `%s`. Please use one of the following: %s',
            value_name,
            value,
            ', '.join(
                '{}: {}'.format(title, tag)
                for tag, title in valid_values.items()
            )
        )
        return False

    return True


def validate_tags(client, agency, route, stop):
    """Validate provided tags."""
    # Validate agencies
    if not validate_value(
            'agency',
            agency,
            client.get_agency_list()['agency'],
    ):
        return False

    # Validate the route
    if not validate_value(
            'route',
            route,
            client.get_route_list(agency)['route'],
    ):
        return False

    # Validate the stop
    route_config = client.get_route_config(route, agency)['route']
    if not validate_value(
            'stop',
            stop,
            route_config['stop'],
    ):
        return False

    return True


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Load values from configuration and initialize the platform."""
    agency = config[CONF_AGENCY]
    route = config[CONF_ROUTE]
    stop = config[CONF_STOP]
    name = config.get(CONF_NAME)

    from py_nextbus import NextBusClient
    client = NextBusClient(output_format='json')

    # Ensures that the tags provided are valid, also logs out valid values
    if not validate_tags(client, agency, route, stop):
        _LOGGER.error('Invalid config value(s)')
        return

    add_entities([
        NextBusDepartureSensor(
            agency,
            route,
            stop,
            name,
            client=client,
        ),
    ], True)


class NextBusDepartureSensor(Entity):
    """Sensor class that displays upcoming NextBus times.

    To function, this requires knowing the agency tag as well as the tags for
    both the route and the stop.

    This is possibly a little convoluted to provide as it requires making a
    request to the service to get these values. Perhaps it can be simplifed in
    the future using fuzzy logic and matching.
    """

    def __init__(self, agency, route, stop, name=None, client=None):
        """Initialize sensor with all required config."""
        self.agency = agency
        self.route = route
        self.stop = stop
        self._custom_name = name
        # Maybe pull a more user friendly name from the API here
        self._name = '{} {}'.format(agency, route)
        self._client = client

        # set up default state attributes
        self._state = None
        self._attributes = {}

    def _log_debug(self, message, *args):
        """Log debug message with prefix."""
        _LOGGER.debug(':'.join((
            self.agency,
            self.route,
            self.stop,
            message,
        )), *args)

    @property
    def name(self):
        """Return sensor name.

        Uses an auto generated name based on the data from the API unless a
        custom name is provided in the configuration.
        """
        if self._custom_name:
            return self._custom_name

        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def state(self):
        """Return current state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return additional state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return icon to be used for this sensor."""
        # Would be nice if we could determine if the line is a train or bus
        # however that doesn't seem to be available to us. Using bus for now.
        return ICON

    def update(self):
        """Update sensor with new departures times."""
        # Note: using Multi because there is a bug with the single stop impl
        predictions = self._client.get_predictions_for_multi_stops(
            [{
                'stop_tag': int(self.stop),
                'route_tag': self.route,
            }],
            self.agency,
        )

        self._log_debug('Predictions results: %s', predictions)

        if 'Error' in predictions:
            self._log_debug('Could not get predictions: %s', predictions)

        if not predictions.get('predictions'):
            self._log_debug('No predictions available')
            self._state = None
            # Remove attributes that may now be outdated
            self._attributes.pop('upcoming', None)
            return

        predictions = predictions['predictions']

        # Set detailed attributes
        self._attributes.update({
            'agency': predictions.get('agencyTitle'),
            'route': predictions.get('routeTitle'),
            'direction': predictions.get('direction', {}).get('title'),
            'stop': predictions.get('stopTitle'),
        })

        # Sometimes message will return a dict, others a list of dicts
        message = predictions.get('message')
        if isinstance(message, dict):
            self._attributes['message'] = message.get('text', '')
        elif isinstance(message, list):
            self._attributes['message'] = ' -- '.join(
                m.get('text', '')
                for m in message
            )
        else:
            self._attributes.pop('message', None)

        upcoming = predictions.get('direction', {}).get('prediction')
        if not upcoming:
            self._log_debug('No upcoming predictions available')
            self._state = None
            self._attributes['upcoming'] = 'No upcoming predictions'
            return

        self._attributes['upcoming'] = ', '.join(
            p['minutes'] for p in upcoming
        )

        latest_prediction = upcoming[0]

        self._state = utc_from_timestamp(
            int(latest_prediction['epochTime']) / 1000
        ).isoformat()
