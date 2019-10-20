"""Platform for sensor integration."""
from datetime import timedelta
import logging

import voluptuous as vol

from pseg import Meter
from pseg import MeterError

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_ENERGIZE_ID = "energize_id"
CONF_ACCESS_TOKEN = "session_id"

SCAN_INTERVAL = timedelta(minutes=60)

ENERGY_THERMS = "therms"
COST_DOLLARS = "$"

SENSOR_NAME_GAS_CONSUMPTION = "PSEG Gas Consumption"
SENSOR_ICON_GAS_CONSUMPTION = "mdi:counter"
SENSOR_NAME_GAS_COST = "PSEG Gas Cost"
SENSOR_ICON_GAS_COST = "mdi:currency-usd"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENERGIZE_ID): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    energize_id = config[CONF_ENERGIZE_ID]
    session_id = config[CONF_ACCESS_TOKEN]

    _LOGGER.debug("Pseg energize_id = %s, session_id = %s", energize_id, session_id)

    try:
        meter = Meter(energize_id, session_id)

    except MeterError:
        _LOGGER.error("Unable to create Pseg meter")
        return

    add_entities([GasConsumptionSensor(meter), GasCostSensor(meter)], True)


class GasConsumptionSensor(Entity):
    """Representation of the Gas Consumption sensor."""

    def __init__(self, meter):
        """Initialize the sensor."""
        self._state = None
        self._available = None
        self.meter = meter

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return self.meter.energize_id + "_consumption"

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_NAME_GAS_CONSUMPTION

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return SENSOR_ICON_GAS_CONSUMPTION

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_THERMS

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._state = self.meter.last_gas_read_consumption()
            self._available = True

            _LOGGER.debug(
                "%s = %s %s", self.name, self._state, self.unit_of_measurement
            )
        except MeterError as err:
            self._available = False

            _LOGGER.error("Unexpected pseg meter error: %s", err)


class GasCostSensor(Entity):
    """Representation of the Gas Cost sensor."""

    def __init__(self, meter):
        """Initialize the sensor."""
        self._state = None
        self._available = None
        self.meter = meter

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return self.meter.energize_id + "_cost"

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_NAME_GAS_COST

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return SENSOR_ICON_GAS_COST

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return COST_DOLLARS

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._state = self.meter.last_gas_read_cost()
            self._available = True

            _LOGGER.debug(
                "%s = %s %s", self.name, self._state, self.unit_of_measurement
            )
        except MeterError as err:
            self._available = False

            _LOGGER.error("Unexpected pseg meter error: %s", err)
