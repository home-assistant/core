"""
homeassistant.util.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Template utility methods for rendering strings with HA data.
"""
# pylint: disable=too-few-public-methods
import json
from jinja2.sandbox import ImmutableSandboxedEnvironment


def render_with_possible_json_value(hass, template, value):
    """ Renders template with value exposed.
        If valid JSON will expose value_json too. """
    variables = {
        'value': value
    }
    try:
        variables['value_json'] = json.loads(value)
    except ValueError:
        pass

    return render(hass, template, variables)


def render(hass, template, variables=None, **kwargs):
    """ Render given template. """
    if variables is not None:
        kwargs.update(variables)

    return ENV.from_string(template, {
        'states': AllStates(hass)
    }).render(kwargs)


class AllStates(object):
    """ Class to expose all HA states as attributes. """
    def __init__(self, hass):
        self._hass = hass

    def __getattr__(self, name):
        return DomainStates(self._hass, name)

    def __iter__(self):
        return iter(sorted(self._hass.states.all(),
                           key=lambda state: state.entity_id))


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


def forgiving_round(value, precision=0):
    """ Rounding method that accepts strings. """
    try:
        return int(float(value)) if precision == 0 else round(float(value),
                                                              precision)
    except ValueError:
        # If value can't be converted to float
        return value


def multiply(value, amount):
    """ Converts to float and multiplies value. """
    try:
        return float(value) * amount
    except ValueError:
        # If value can't be converted to float
        return value

ENV = ImmutableSandboxedEnvironment()
ENV.filters['round'] = forgiving_round
ENV.filters['multiply'] = multiply
