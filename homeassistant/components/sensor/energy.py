"""
Energy meter from a power sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.energy/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (DOMAIN, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, ATTR_UNIT_OF_MEASUREMENT, ATTR_ENTITY_ID)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

ATTR_PERIODICITY = 'periodicity'  # TODO reset meter periodically

CONF_POWER_SENSOR = 'power_sensor'
CONF_ROUND_DIGITS = 'round'

UNIT_WATTS = "W"
UNIT_KILOWATTS = "kW"

ICON = 'mdi:counter'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_POWER_SENSOR): cv.entity_id,
    vol.Optional(CONF_ROUND_DIGITS, default=8): vol.Coerce(int),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the energy sensor."""
    meter = EnergySensor(hass, config[CONF_POWER_SENSOR],
                  config.get(CONF_NAME),
                  config[CONF_ROUND_DIGITS])
    
    async_add_entities([meter])

    def reset_meter(service):
        _LOGGER.debug(service.data.get('entity_id'))
        meter.reset()
    hass.services.async_register(DOMAIN, "reset_meter", reset_meter)

class EnergySensor(RestoreEntity):
    """Representation of an energy sensor."""

    def __init__(self, hass, entity_id, name, round_digits):
        """Initialize the min/max sensor."""
        self._hass = hass
        self._power_sensor_id = entity_id
        self._round_digits = round_digits
        self._state = 0

        if name:
            self._name = name
        else:
            self._name = '{} meter'.format(entity_id)

        self._unit_of_measurement = "kWh"
        self._unit_of_measurement_scale = None

    def reset(self):
        self._state = 0

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._state = float(state.state)

        @callback
        def async_calc_energy(entity, old_state, new_state):
            """Handle the sensor state changes."""
            if old_state is None:
                return

            if self._unit_of_measurement_scale is None:
                unit_of_measurement = new_state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT)
                if unit_of_measurement == UNIT_WATTS:
                    self._unit_of_measurement_scale = 1000
                if unit_of_measurement == UNIT_KILOWATTS:
                    self._unit_of_measurement_scale = 1

            try:
                # energy as the Riemann integral of previous measures.
                elapsed_time = (new_state.last_updated
                                - old_state.last_updated).total_seconds()
                area = (float(new_state.state)
                        + float(old_state.state))*elapsed_time/2
                kwh = area / (self._unit_of_measurement_scale * 3600)
                self._state += kwh

            except ValueError:
                _LOGGER.warning("Unable to store state. "
                                "Only numerical states are supported")

            self._hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            self._hass, self._power_sensor_id, async_calc_energy)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self._state, self._round_digits)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_ENTITY_ID: self._power_sensor_id
        }
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON
