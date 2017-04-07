"""
Support for keeping a simple counter.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.counter/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_INITIAL = 'initial'
CONF_STEP = 'step'

DEFAULT_NAME = 'Counter'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_INITIAL, default=0): vol.Coerce(int),
    vol.Optional(CONF_STEP, default=1): vol.Coerce(int)
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    data = CounterData(hass, config)
    sensor = CounterSensor(data, config.get(CONF_NAME))
    add_devices([sensor])

    def increment_counter(call=None):
        """Increment counter and update sensor."""
        data.increment()
        sensor.update()

    def decrement_counter(call=None):
        """Decrement counter and update sensor."""
        data.decrement()
        sensor.update()

    def reset_counter(call=None):
        """Reset counter and update sensor."""
        data.reset()
        sensor.update()

    hass.services.register(DOMAIN, 'counter_increment', increment_counter)
    hass.services.register(DOMAIN, 'counter_reset', reset_counter)
    hass.services.register(DOMAIN, 'counter_decrement', decrement_counter)


class CounterSensor(Entity):
    """Representation of a counter sensor."""

    def __init__(self, counter_data, name):
        """Initialize the sensor."""
        self.counter_client = counter_data
        self._state = self.counter_client.count
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest value from the data client."""
        self._state = self.counter_client.count


class CounterData(object):
    """Keep all counter data and actions."""

    def __init__(self, hass, config):
        """Initialize the data client."""
        self._initial = config[CONF_INITIAL]
        self._step = config[CONF_STEP]
        self.count = self._initial

    def increment(self):
        """Increment the counter."""
        _LOGGER.debug('Incrementing counter')
        self.count += self._step

    def decrement(self):
        """Decrement the counter."""
        _LOGGER.debug('Decrementing counter')
        self.count -= self._step

    def reset(self):
        """Reset the counter."""
        _LOGGER.debug('Resetting counter')
        self.count = self._initial
