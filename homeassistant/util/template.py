"""
homeassistant.util.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Template utility methods for rendering strings with HA data.
"""
# pylint: disable=too-few-public-methods
import json
import logging

import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

from homeassistant.const import STATE_UNKNOWN, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import State
from homeassistant.exceptions import TemplateError
from homeassistant.util import convert, dt as dt_util, location

_LOGGER = logging.getLogger(__name__)
_SENTINEL = object()


def render_with_possible_json_value(hass, template, value,
                                    error_value=_SENTINEL):
    """ Renders template with value exposed.
        If valid JSON will expose value_json too. """
    variables = {
        'value': value
    }
    try:
        variables['value_json'] = json.loads(value)
    except ValueError:
        pass

    try:
        return render(hass, template, variables)
    except TemplateError:
        _LOGGER.exception('Error parsing value')
        return value if error_value is _SENTINEL else error_value


def render(hass, template, variables=None, **kwargs):
    """ Render given template. """
    if variables is not None:
        kwargs.update(variables)

    location_helper = LocationHelpers(hass)
    utcnow = dt_util.utcnow()

    try:
        return ENV.from_string(template, {
            'distance': location_helper.distance,
            'is_state': hass.states.is_state,
            'is_state_attr': hass.states.is_state_attr,
            'states': AllStates(hass),
            'now': dt_util.as_local(utcnow),
            'utcnow': utcnow,
        }).render(kwargs).strip()
    except jinja2.TemplateError as err:
        raise TemplateError(err)


class AllStates(object):
    """ Class to expose all HA states as attributes. """
    def __init__(self, hass):
        self._hass = hass

    def __getattr__(self, name):
        return DomainStates(self._hass, name)

    def __iter__(self):
        return iter(sorted(self._hass.states.all(),
                           key=lambda state: state.entity_id))

    def __call__(self, entity_id):
        state = self._hass.states.get(entity_id)
        return STATE_UNKNOWN if state is None else state.state


class DomainStates(object):
    """ Class to expose a specific HA domain as attributes. """

    def __init__(self, hass, domain):
        self._hass = hass
        self._domain = domain

    def __getattr__(self, name):
        return self._hass.states.get('{}.{}'.format(self._domain, name))

    def __iter__(self):
        return iter(sorted(
            (state for state in self._hass.states.all()
             if state.domain == self._domain),
            key=lambda state: state.entity_id))


class LocationHelpers(object):
    """Class to expose distance helpers to templates."""

    def __init__(self, hass):
        """Initialize distance helpers."""
        self._hass = hass

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

        return location.distance(*locations[0] + locations[1])


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


class TemplateEnvironment(ImmutableSandboxedEnvironment):
    """Home Assistant template environment."""

    def is_safe_callable(self, obj):
        """Test if callback is safe."""
        return isinstance(obj, AllStates) or super().is_safe_callable(obj)

ENV = TemplateEnvironment()
ENV.filters['round'] = forgiving_round
ENV.filters['multiply'] = multiply
