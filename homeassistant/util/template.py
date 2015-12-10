"""
homeassistant.util.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Template utility methods for rendering strings with HA data.
"""
# pylint: disable=too-few-public-methods
from jinja2.sandbox import SandboxedEnvironment

ENV = SandboxedEnvironment()


def forgiving_round(value, precision=0):
    """ Rounding method that accepts strings. """
    try:
        return int(value) if precision == 0 else round(float(value), precision)
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

ENV.filters['round'] = forgiving_round
ENV.filters['multiply'] = multiply


def render(hass, template):
    """ Render given template. """
    return ENV.from_string(template).render(
        states=AllStates(hass))


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
