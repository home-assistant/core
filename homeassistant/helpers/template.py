"""Template helper methods for rendering strings with HA data."""
# pylint: disable=too-few-public-methods
import json
import logging

import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

from homeassistant.components import group
from homeassistant.const import STATE_UNKNOWN, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import State
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import location as loc_helper
from homeassistant.util import convert, dt as dt_util, location as loc_util

_LOGGER = logging.getLogger(__name__)
_SENTINEL = object()


def render_with_possible_json_value(hass, template, value,
                                    error_value=_SENTINEL):
    """Render template with value exposed.

    If valid JSON will expose value_json too.
    """
    variables = {
        'value': value
    }
    try:
        variables['value_json'] = json.loads(value)
    except ValueError:
        pass

    try:
        return render(hass, template, variables)
    except TemplateError as ex:
        _LOGGER.error('Error parsing value: %s', ex)
        return value if error_value is _SENTINEL else error_value


def render(hass, template, variables=None, **kwargs):
    """Render given template."""
    if variables is not None:
        kwargs.update(variables)

    location_methods = LocationMethods(hass)
    utcnow = dt_util.utcnow()

    try:
        return ENV.from_string(template, {
            'closest': location_methods.closest,
            'distance': location_methods.distance,
            'float': forgiving_float,
            'is_state': hass.states.is_state,
            'is_state_attr': hass.states.is_state_attr,
            'now': dt_util.as_local(utcnow),
            'states': AllStates(hass),
            'utcnow': utcnow,
            'as_timestamp': dt_util.as_timestamp,
            'relative_time': dt_util.get_age
        }).render(kwargs).strip()
    except jinja2.TemplateError as err:
        raise TemplateError(err)


class AllStates(object):
    """Class to expose all HA states as attributes."""

    def __init__(self, hass):
        """Initialize all states."""
        self._hass = hass

    def __getattr__(self, name):
        """Return the domain state."""
        return DomainStates(self._hass, name)

    def __iter__(self):
        """Return all states."""
        return iter(sorted(self._hass.states.all(),
                           key=lambda state: state.entity_id))

    def __call__(self, entity_id):
        """Return the states."""
        state = self._hass.states.get(entity_id)
        return STATE_UNKNOWN if state is None else state.state


class DomainStates(object):
    """Class to expose a specific HA domain as attributes."""

    def __init__(self, hass, domain):
        """Initialize the domain states."""
        self._hass = hass
        self._domain = domain

    def __getattr__(self, name):
        """Return the states."""
        return self._hass.states.get('{}.{}'.format(self._domain, name))

    def __iter__(self):
        """Return the iteration over all the states."""
        return iter(sorted(
            (state for state in self._hass.states.all()
             if state.domain == self._domain),
            key=lambda state: state.entity_id))


class LocationMethods(object):
    """Class to expose distance helpers to templates."""

    def __init__(self, hass):
        """Initialize the distance helpers."""
        self._hass = hass

    def closest(self, *args):
        """Find closest entity.

        Closest to home:
          closest(states)
          closest(states.device_tracker)
          closest('group.children')
          closest(states.group.children)

        Closest to a point:
          closest(23.456, 23.456, 'group.children')
          closest('zone.school', 'group.children')
          closest(states.zone.school, 'group.children')
        """
        if len(args) == 1:
            latitude = self._hass.config.latitude
            longitude = self._hass.config.longitude
            entities = args[0]

        elif len(args) == 2:
            point_state = self._resolve_state(args[0])

            if point_state is None:
                _LOGGER.warning('Closest:Unable to find state %s', args[0])
                return None
            elif not loc_helper.has_location(point_state):
                _LOGGER.warning(
                    'Closest:State does not contain valid location: %s',
                    point_state)
                return None

            latitude = point_state.attributes.get(ATTR_LATITUDE)
            longitude = point_state.attributes.get(ATTR_LONGITUDE)

            entities = args[1]

        else:
            latitude = convert(args[0], float)
            longitude = convert(args[1], float)

            if latitude is None or longitude is None:
                _LOGGER.warning(
                    'Closest:Received invalid coordinates: %s, %s',
                    args[0], args[1])
                return None

            entities = args[2]

        if isinstance(entities, (AllStates, DomainStates)):
            states = list(entities)
        else:
            if isinstance(entities, State):
                gr_entity_id = entities.entity_id
            else:
                gr_entity_id = str(entities)

            states = [self._hass.states.get(entity_id) for entity_id
                      in group.expand_entity_ids(self._hass, [gr_entity_id])]

        return loc_helper.closest(latitude, longitude, states)

    def distance(self, *args):
        """Calculate distance.

        Will calculate distance from home to a point or between points.
        Points can be passed in using state objects or lat/lng coordinates.
        """
        locations = []

        to_process = list(args)

        while to_process:
            value = to_process.pop(0)

            if isinstance(value, State):
                latitude = value.attributes.get(ATTR_LATITUDE)
                longitude = value.attributes.get(ATTR_LONGITUDE)

                if latitude is None or longitude is None:
                    _LOGGER.warning(
                        'Distance:State does not contains a location: %s',
                        value)
                    return None

            else:
                # We expect this and next value to be lat&lng
                if not to_process:
                    _LOGGER.warning(
                        'Distance:Expected latitude and longitude, got %s',
                        value)
                    return None

                value_2 = to_process.pop(0)
                latitude = convert(value, float)
                longitude = convert(value_2, float)

                if latitude is None or longitude is None:
                    _LOGGER.warning('Distance:Unable to process latitude and '
                                    'longitude: %s, %s', value, value_2)
                    return None

            locations.append((latitude, longitude))

        if len(locations) == 1:
            return self._hass.config.distance(*locations[0])

        return loc_util.distance(*locations[0] + locations[1])

    def _resolve_state(self, entity_id_or_state):
        """Return state or entity_id if given."""
        if isinstance(entity_id_or_state, State):
            return entity_id_or_state
        elif isinstance(entity_id_or_state, str):
            return self._hass.states.get(entity_id_or_state)
        return None


def forgiving_round(value, precision=0):
    """Rounding filter that accepts strings."""
    try:
        value = round(float(value), precision)
        return int(value) if precision == 0 else value
    except (ValueError, TypeError):
        # If value can't be converted to float
        return value


def multiply(value, amount):
    """Filter to convert value to float and multiply it."""
    try:
        return float(value) * amount
    except (ValueError, TypeError):
        # If value can't be converted to float
        return value


def forgiving_float(value):
    """Try to convert value to a float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return value


class TemplateEnvironment(ImmutableSandboxedEnvironment):
    """The Home Assistant template environment."""

    def is_safe_callable(self, obj):
        """Test if callback is safe."""
        return isinstance(obj, AllStates) or super().is_safe_callable(obj)

ENV = TemplateEnvironment()
ENV.filters['round'] = forgiving_round
ENV.filters['multiply'] = multiply
