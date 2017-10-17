"""
Support for monitoring the state of Digital Ocean droplets.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.digital_ocean/
"""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.vultr import (
    CONF_SUBS, ATTR_CURRENT_BANDWIDTH_GB, ATTR_PENDING_CHARGES, DATA_VULTR)

DEFAULT_NAME = 'Vultr_Server'
DEPENDENCIES = ['vultr']

MONITORED_CONDITIONS = {
    ATTR_CURRENT_BANDWIDTH_GB: ['Current Bandwidth Used', 'GB',
                                'mdi:chart-histogram'],
    ATTR_PENDING_CHARGES: ['Pending Charges', 'US$',
                           'mdi:currency-usd']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SUBS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_MONITORED_CONDITIONS, default=MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Vultr subscription (server) sensor."""
    vultr = hass.data.get(DATA_VULTR)
    if not vultr:
        return False

    subscriptions = config.get(CONF_SUBS)

    sensors = []

    for subscription in subscriptions:
        sensors += [VultrSensor(vultr, subscription, condition)
                    for condition in config[CONF_MONITORED_CONDITIONS]]

    add_devices(sensors, True)


class VultrSensor(Entity):
    """Representation of a Vultr subscription sensor."""

    def __init__(self, vultr, subscription, variable):
        """Initialize a new Vultr sensor."""
        self._vultr = vultr
        self._subscription = subscription
        self._var_id = variable
        self.data = self._vultr.data.get(self._subscription, {})

        variable_info = MONITORED_CONDITIONS[variable]

        self._var_name = variable_info[0]
        self._var_units = variable_info[1]
        self._var_icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self.data.get('label', DEFAULT_NAME),
                              self._var_name)

    @property
    def icon(self):
        """Icon used in the frontend if any."""
        return self._var_icon

    @property
    def unit_of_measurement(self):
        """The unit of measurement to present the value in."""
        return self._var_units

    @property
    def state(self):
        """Return true if the binary sensor is on."""
        try:
            return round(float(self.data.get(self._var_id)), 2)
        except TypeError:
            return self.data.get(self._var_id)

    def update(self):
        """Update state of sensor."""
        self._vultr.update()
        self.data = self._vultr.data.get(self._subscription, {})
