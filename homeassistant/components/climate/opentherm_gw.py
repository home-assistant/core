import asyncio
import logging
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_MAX_TEMP, ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_STEP,
    ClimateDevice, PLATFORM_SCHEMA, STATE_IDLE, STATE_HEAT, STATE_COOL,
    SUPPORT_AWAY_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW,
    SUPPORT_ON_OFF)
from homeassistant.components.climate.modbus import CONF_PRECISION
from homeassistant.const import (ATTR_TEMPERATURE, CONF_DEVICE, CONF_NAME,
    PRECISION_HALVES, PRECISION_TENTHS, TEMP_CELSIUS, PRECISION_WHOLE,
    STATE_ON, STATE_OFF)
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyotgw']

CONF_FLOOR_TEMP = "floor_temperature"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE): cv.string,
    vol.Optional(CONF_NAME, default="Opentherm Gateway"): cv.string,
    vol.Optional(CONF_PRECISION): vol.In([PRECISION_TENTHS, PRECISION_HALVES,
                                         PRECISION_WHOLE]),
    vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
})

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)
_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the opentherm_gw component."""
    gw = opentherm_gw()
    gw.friendly_name = config.get(CONF_NAME)
    gw._floor_temp = config.get(CONF_FLOOR_TEMP, False)
    gw._precision = config.get(CONF_PRECISION)
    async_add_entities([gw])
    await gw.connect(hass, config.get(CONF_DEVICE))
    _LOGGER.debug("Connected to {} on {}".format(gw.friendly_name,
                                                 config.get(CONF_DEVICE)))
    return True

class opentherm_gw(ClimateDevice):
    """Representation of a climate device."""

    def __init__(self):
        """Initialize the sensor."""
        import pyotgw
        self.pyotgw = pyotgw
        self._current_operation = STATE_IDLE
        self._current_temperature = 0.0
        self._target_temperature = 0.0

    async def connect(self, hass, gw_path):
        self.gw = self.pyotgw.pyotgw()
        self.hass = hass
        await self.gw.connect(hass.loop, gw_path)
        self.gw.subscribe(self.receive_report)
        return

    async def receive_report(self, status):
        _LOGGER.debug("Received report: {}".format(status))
        ch_active = status.get(self.pyotgw.DATA_SLAVE_CH_ACTIVE)
        cooling_active = status.get(self.pyotgw.DATA_SLAVE_COOLING_ACTIVE)
        if ch_active:
            self._current_operation = STATE_HEAT
        elif cooling_active:
            self._current_operation = STATE_COOL
        else:
            self._current_operation = STATE_IDLE
        self._current_temperature = status.get(self.pyotgw.DATA_ROOM_TEMP)
        self._target_temperature = (status.get(self.pyotgw.DATA_ROOM_SETPOINT)
            if status.get(self.pyotgw.DATA_ROOM_SETPOINT_OVRD, 0) == 0
            else status.get(self.pyotgw.DATA_ROOM_SETPOINT_OVRD))

        if (status.get(self.pyotgw.OTGW_GPIO_A) == 5):
            self._away_mode_a = 0
        elif (status.get(self.pyotgw.OTGW_GPIO_A) == 6):
            self._away_mode_a = 1
        else:
            self._away_mode_a = None
        if (status.get(self.pyotgw.OTGW_GPIO_B) == 5):
            self._away_mode_b = 0
        elif (status.get(self.pyotgw.OTGW_GPIO_B) == 6):
            self._away_mode_b = 1
        else:
            self._away_mode_b = None
        if self._away_mode_a is not None:
            self._away_state_a = (status.get(self.pyotgw.OTGW_GPIO_A_STATE) ==
                                  self._away_mode_a)
        if self._away_mode_b is not None:
            self._away_state_b = (status.get(self.pyotgw.OTGW_GPIO_B_STATE) ==
                                  self._away_mode_b)
        self.hass.async_add_job(self.async_update_ha_state(True))

    @property
    def name(self):
        return self.friendly_name

    @property
    def state(self):
        """Return the current state."""
        if self.is_on is False:
            return STATE_OFF
        if self._current_operation:
            return self._current_operation
        if self.is_on:
            return STATE_ON
        return STATE_UNKNOWN

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._precision is not None:
            return self._precision
        if self.unit_of_measurement == TEMP_CELSIUS:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to display."""
        return self.hass.config.units.temperature_unit

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._floor_temp is True:
            if self._precision == PRECISION_HALVES:
                return int(2 * self._current_temperature) / 2
            elif self._precision == PRECISION_TENTHS:
                return int(10 * self._current_temperature) / 10
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.precision

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return (getattr(self, '_away_state_a', False) or
                getattr(self, '_away_state_b', False))

    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if 'temperature' in kwargs:
            temp = float(kwargs['temperature'])
            return self.gw.set_target_temp(temp)
        else:
            return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (SUPPORT_TARGET_TEMPERATURE)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(1, TEMP_CELSIUS, self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(30, TEMP_CELSIUS, self.temperature_unit)
