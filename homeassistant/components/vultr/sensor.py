"""
Support for monitoring the state of Vultr Subscriptions.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.vultr/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import (
    ATTR_CURRENT_BANDWIDTH_USED, ATTR_PENDING_CHARGES, CONF_SUBSCRIPTION,
    DATA_VULTR)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Vultr {} {}'
DEPENDENCIES = ['vultr']

MONITORED_CONDITIONS = {
    ATTR_CURRENT_BANDWIDTH_USED: ['Current Bandwidth Used', 'GB',
                                  'mdi:chart-histogram'],
    ATTR_PENDING_CHARGES: ['Pending Charges', 'US$', 'mdi:currency-usd'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SUBSCRIPTION): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=list(MONITORED_CONDITIONS)):
    vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Vultr subscription (server) sensor."""
    vultr = hass.data[DATA_VULTR]

    subscription = config.get(CONF_SUBSCRIPTION)
    name = config.get(CONF_NAME)
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)

    if subscription not in vultr.data:
        _LOGGER.error("Subscription %s not found", subscription)
        return

    sensors = []

    for condition in monitored_conditions:
        sensors.append(VultrSensor(vultr, subscription, condition, name))

    add_entities(sensors, True)


class VultrSensor(Entity):
    """Representation of a Vultr subscription sensor."""

    def __init__(self, vultr, subscription, condition, name):
        """Initialize a new Vultr sensor."""
        self._vultr = vultr
        self._condition = condition
        self._name = name

        self.subscription = subscription
        self.data = None

        condition_info = MONITORED_CONDITIONS[condition]

        self._condition_name = condition_info[0]
        self._units = condition_info[1]
        self._icon = condition_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        try:
            return self._name.format(self._condition_name)
        except IndexError:
            try:
                return self._name.format(
                    self.data['label'], self._condition_name)
            except (KeyError, TypeError):
                return self._name

    @property
    def icon(self):
        """Return the icon used in the frontend if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to present the value in."""
        return self._units

    @property
    def state(self):
        """Return the value of this given sensor type."""
        try:
            return round(float(self.data.get(self._condition)), 2)
        except (TypeError, ValueError):
            return self.data.get(self._condition)

    def update(self):
        """Update state of sensor."""
        self._vultr.update()
        self.data = self._vultr.data[self.subscription]
