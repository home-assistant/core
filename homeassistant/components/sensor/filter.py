"""
Support for filtering for sensor values.

Example configuration:

sensor:
  - platform: simulated
    name: 'simulated relative humidity'
    unit: '%'
    amplitude: 0 # Turns off sine wave
    mean: 50
    spread: 10
    seed: 999

  - platform: filter
    entity_id: sensor.simulated_relative_humidity
    name: lowpass
    options:
      time_constant: 10

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.filter/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.filter import (
    Filter, FILTER_LOWPASS, FILTER_OUTLIER)
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

ATTR_FILTER = 'filter'
ATTR_PRE_FILTER = 'pre_filter_state'

CONF_FILTER_OPTIONS = 'options'
CONF_FILTER_NAME = 'filter'

TYPE_LOWPASS = 'lowpass'
TYPE_OUTLIER = 'outlier'

FILTER_MAP = {
             TYPE_LOWPASS: FILTER_LOWPASS,
             TYPE_OUTLIER: FILTER_OUTLIER,
             }

DEFAULT_NAME_TEMPLATE = "{} filter {}"
ICON = 'mdi: chart-line-variant'

# ALL filter arguments must be OPTIONAL
FILTER_SCHEMA = vol.Schema({
    vol.Optional('time_constant'): vol.Coerce(int),
    vol.Optional('constant'): vol.Coerce(int)
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_FILTER_NAME):
        vol.Any(TYPE_LOWPASS, TYPE_OUTLIER),
    vol.Optional(CONF_FILTER_OPTIONS): FILTER_SCHEMA,
    vol.Optional(CONF_NAME, default=None): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Filter sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    filter_name = config.get(CONF_FILTER_NAME)
    name = config.get(CONF_NAME)
    if name is None:
        name = DEFAULT_NAME_TEMPLATE.format(entity_id, filter_name)

    async_add_devices([
            FilterSensor(hass, name, entity_id, filter_name,
                         config.get(CONF_FILTER_OPTIONS, dict()))
        ], True)
    return True


class FilterSensor(Entity):
    """Representation of a Filter sensor."""

    def __init__(self, hass, name, entity_id, filter_name, filter_args):
        """Initialize the Filter sensor."""
        self._name = name
        self._filter_name = filter_name
        self._unit_of_measurement = None
        self._pre_filter_state = self._state = None

        self._filterdata = self.filterdata_factory(FILTER_MAP[filter_name],
                                                   **filter_args)()

        @callback
        # pylint: disable=invalid-name
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT)

            if new_state.state is None or new_state.state is STATE_UNKNOWN:
                return

            try:
                self._pre_filter_state = new_state.state
                self._filterdata.update(self._pre_filter_state)
            except ValueError:
                _LOGGER.error("This component can only filter numbers")
                return

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_stats_sensor_state_listener)

    @property
    def available(self):
        """Return True if there is data to filter."""
        return self._pre_filter_state is not None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._filterdata.data

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_FILTER: self._filter_name,
            ATTR_PRE_FILTER: self._pre_filter_state,
            ATTR_UNIT_OF_MEASUREMENT: self._unit_of_measurement
        }
        return state_attr

    def filterdata_factory(self, filter_function, **kwargs):
        """Factory to create filters with user provided arguments."""
        class FilterData(object):
            def __init__(self):
                self._data = None

            @property
            @Filter(filter_function, **kwargs)
            def data(self):
                return self._data

            def update(self, new_data):
                self._data = float(new_data)

        return FilterData
