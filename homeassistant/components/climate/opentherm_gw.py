"""OpenTherm Gateway Climate component for Home Assistant."""

import logging
import voluptuous as vol

from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA,
                                              STATE_IDLE, STATE_HEAT,
                                              STATE_COOL,
                                              SUPPORT_TARGET_TEMPERATURE)
from homeassistant.components.climate.modbus import CONF_PRECISION
from homeassistant.const import (CONF_DEVICE, CONF_NAME, PRECISION_HALVES,
                                 PRECISION_TENTHS, TEMP_CELSIUS,
                                 PRECISION_WHOLE, STATE_ON, STATE_OFF,
                                 STATE_UNKNOWN)
from homeassistant.util.temperature import convert as convert_temperature
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyotgw==0.1a0']

CONF_FLOOR_TEMP = "floor_temperature"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE): cv.string,
    vol.Optional(CONF_NAME, default="OpenTherm Gateway"): cv.string,
    vol.Optional(CONF_PRECISION): vol.In([PRECISION_TENTHS, PRECISION_HALVES,
                                          PRECISION_WHOLE]),
    vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
})

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the opentherm_gw component."""
    gateway = OpenThermGateway()
    gateway.friendly_name = config.get(CONF_NAME)
    gateway.floor_temp = config.get(CONF_FLOOR_TEMP, False)
    gateway.temp_precision = config.get(CONF_PRECISION)
    async_add_entities([gateway])
    await gateway.connect(hass, config.get(CONF_DEVICE))
    _LOGGER.debug("Connected to %s on %s", gateway.friendly_name,
                  config.get(CONF_DEVICE))
    return True


class OpenThermGateway(ClimateDevice):
    """Representation of a climate device."""

    def __init__(self):
        """Initialize the sensor."""
        import pyotgw
        self.pyotgw = pyotgw
        self._current_operation = STATE_IDLE
        self._current_temperature = 0.0
        self._target_temperature = 0.0
        self.gateway = self.pyotgw.pyotgw()
        self.friendly_name = "OpenTherm Gateway"
        self.floor_temp = False
        self.temp_precision = None
        self._away_mode_a = None
        self._away_mode_b = None
        self._away_state_a = False
        self._away_state_b = False

    async def connect(self, hass, gw_path):
        """Connect to the OpenTherm Gateway device at gw_path."""
        self.hass = hass
        await self.gateway.connect(hass.loop, gw_path)
        self.gateway.subscribe(self.receive_report)
        return

    async def receive_report(self, status):
        """Receive and handle a new report from the Gateway."""
        _LOGGER.debug("Received report: %s", status)
        ch_active = status.get(self.pyotgw.DATA_SLAVE_CH_ACTIVE)
        cooling_active = status.get(self.pyotgw.DATA_SLAVE_COOLING_ACTIVE)
        if ch_active:
            self._current_operation = STATE_HEAT
        elif cooling_active:
            self._current_operation = STATE_COOL
        else:
            self._current_operation = STATE_IDLE
        self._current_temperature = status.get(self.pyotgw.DATA_ROOM_TEMP)
        if status.get(self.pyotgw.DATA_ROOM_SETPOINT_OVRD, 0) == 0:
            temp = status.get(self.pyotgw.DATA_ROOM_SETPOINT)
        else:
            temp = status.get(self.pyotgw.DATA_ROOM_SETPOINT_OVRD)
        self._target_temperature = temp

        # GPIO mode 5: 0 == Away
        # GPIO mode 6: 1 == Away
        if status.get(self.pyotgw.OTGW_GPIO_A) == 5:
            self._away_mode_a = 0
        elif status.get(self.pyotgw.OTGW_GPIO_A) == 6:
            self._away_mode_a = 1
        else:
            self._away_mode_a = None
        if status.get(self.pyotgw.OTGW_GPIO_B) == 5:
            self._away_mode_b = 0
        elif status.get(self.pyotgw.OTGW_GPIO_B) == 6:
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
        """Return the friendly name."""
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
        if self.temp_precision is not None:
            return self.temp_precision
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
        if self.floor_temp is True:
            if self.temp_precision == PRECISION_HALVES:
                return int(2 * self._current_temperature) / 2
            if self.temp_precision == PRECISION_TENTHS:
                return int(10 * self._current_temperature) / 10
            return int(self._current_temperature)
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.temp_precision

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return (getattr(self, '_away_state_a', False) or
                getattr(self, '_away_state_b', False))

    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if 'temperature' in kwargs:
            temp = float(kwargs['temperature'])
            return self.gateway.set_target_temp(temp)
        return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(1, TEMP_CELSIUS, self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(30, TEMP_CELSIUS, self.temperature_unit)
