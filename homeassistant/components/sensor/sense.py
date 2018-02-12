"""
Support for monitoring a Sense energy sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sense/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_EMAIL, CONF_PASSWORD)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['sense_energy==0.3.0']

_LOGGER = logging.getLogger(__name__)

ACTIVE_NAME = "Energy"
DAILY_NAME = "Daily"
WEEKLY_NAME = "Weekly"
MONTHLY_NAME = "Monthly"
YEARLY_NAME = "Yearly"

PRODUCTION_NAME = "Production"
CONSUMPTION_NAME = "Usage"

ACTIVE_TYPE = 'active'
DAILY_TYPE = 'DAY'
WEEKLY_TYPE = 'WEEK'
MONTHLY_TYPE = 'MONTH'
YEARLY_TYPE = 'YEAR'

ICON = 'mdi:flash'

MIN_TIME_BETWEEN_DAILY_UPDATES = timedelta(seconds=300)
MIN_TIME_BETWEEN_ACTIVE_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Sense sensor."""
    from sense_energy import Senseable

    username = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)

    data = Senseable(username, password)

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    def update_trends():
        """Update the daily power usage."""
        data.update_trend_data()

    @Throttle(MIN_TIME_BETWEEN_ACTIVE_UPDATES)
    def update_active():
        """Update the active power usage."""
        data.get_realtime()

    add_devices([
        # Active power usage/production
        Sense(data, ACTIVE_NAME, ACTIVE_TYPE, False, update_active),
        Sense(data, ACTIVE_NAME, ACTIVE_TYPE, True, update_active),
        # Daily Power
        Sense(data, DAILY_NAME, DAILY_TYPE, False, update_trends),
        Sense(data, DAILY_NAME, DAILY_TYPE, True, update_trends),
        # Weekly Power
        Sense(data, WEEKLY_NAME, WEEKLY_TYPE, False, update_trends),
        Sense(data, WEEKLY_NAME, WEEKLY_TYPE, True, update_trends),
        # Monthly Power
        Sense(data, MONTHLY_NAME, MONTHLY_TYPE, False, update_trends),
        Sense(data, MONTHLY_NAME, MONTHLY_TYPE, True, update_trends),
        # Yearly Power
        Sense(data, YEARLY_NAME, YEARLY_TYPE, False, update_trends),
        Sense(data, YEARLY_NAME, YEARLY_TYPE, True, update_trends),
        ])


class Sense(Entity):
    """Implementation of a Sense energy sensor."""

    def __init__(self, data, name, sensor_type, is_production, update_call):
        """Initialize the sensor."""
        name_type = PRODUCTION_NAME if is_production else CONSUMPTION_NAME
        self._name = "%s %s" % (name, name_type)
        self._data = data
        self._sensor_type = sensor_type
        self.update_sensor = update_call
        self._is_production = is_production
        self._state = None

        if sensor_type == ACTIVE_TYPE:
            self._unit_of_measurement = 'W'
        else:
            self._unit_of_measurement = 'kWh'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data, update state."""
        self.update_sensor()

        if self._sensor_type == ACTIVE_TYPE:
            if self._is_production:
                self._state = round(self._data.active_solar_power)
            else:
                self._state = round(self._data.active_power)
        else:
            state = self._data.get_trend(self._sensor_type,
                                         self._is_production)
            self._state = round(state, 1)
