"""
Support for OpenTherm Gateway devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/climate.opentherm_gw/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA,
                                              STATE_IDLE, STATE_HEAT,
                                              STATE_COOL,
                                              SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (ATTR_TEMPERATURE, CONF_DEVICE, CONF_NAME,
                                 PRECISION_HALVES, PRECISION_TENTHS,
                                 TEMP_CELSIUS, PRECISION_WHOLE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyotgw==0.1b0']

CONF_FLOOR_TEMP = "floor_temperature"
CONF_PRECISION = 'precision'

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
    """Set up the opentherm_gw device."""
    gateway = OpenThermGateway(config)
    async_add_entities([gateway])


class OpenThermGateway(ClimateDevice):
    """Representation of a climate device."""

    def __init__(self, config):
        """Initialize the sensor."""
        import pyotgw
        self.pyotgw = pyotgw
        self.gateway = self.pyotgw.pyotgw()
        self._device = config[CONF_DEVICE]
        self.friendly_name = config.get(CONF_NAME)
        self.floor_temp = config.get(CONF_FLOOR_TEMP)
        self.temp_precision = config.get(CONF_PRECISION)
        self._current_operation = STATE_IDLE
        self._current_temperature = 0.0
        self._target_temperature = 0.0
        self._away_mode_a = None
        self._away_mode_b = None
        self._away_state_a = False
        self._away_state_b = False

    async def async_added_to_hass(self):
        """Connect to the OpenTherm Gateway device."""
        await self.gateway.connect(self.hass.loop, self._device)
        self.gateway.subscribe(self.receive_report)
        _LOGGER.debug("Connected to %s on %s", self.friendly_name,
                      self._device)

    async def receive_report(self, status):
        """Receive and handle a new report from the Gateway."""
        _LOGGER.debug("Received report: %s", status)
        ch_active = status.get(self.pyotgw.DATA_SLAVE_CH_ACTIVE)
        flame_on = status.get(self.pyotgw.DATA_SLAVE_FLAME_ON)
        cooling_active = status.get(self.pyotgw.DATA_SLAVE_COOLING_ACTIVE)
        if ch_active and flame_on:
            self._current_operation = STATE_HEAT
        elif cooling_active:
            self._current_operation = STATE_COOL
        else:
            self._current_operation = STATE_IDLE
        self._current_temperature = status.get(self.pyotgw.DATA_ROOM_TEMP)

        temp = status.get(self.pyotgw.DATA_ROOM_SETPOINT_OVRD)
        if temp is None:
            temp = status.get(self.pyotgw.DATA_ROOM_SETPOINT)
        self._target_temperature = temp

        # GPIO mode 5: 0 == Away
        # GPIO mode 6: 1 == Away
        gpio_a_state = status.get(self.pyotgw.OTGW_GPIO_A)
        if gpio_a_state == 5:
            self._away_mode_a = 0
        elif gpio_a_state == 6:
            self._away_mode_a = 1
        else:
            self._away_mode_a = None
        gpio_b_state = status.get(self.pyotgw.OTGW_GPIO_B)
        if gpio_b_state == 5:
            self._away_mode_b = 0
        elif gpio_b_state == 6:
            self._away_mode_b = 1
        else:
            self._away_mode_b = None
        if self._away_mode_a is not None:
            self._away_state_a = (status.get(self.pyotgw.OTGW_GPIO_A_STATE) ==
                                  self._away_mode_a)
        if self._away_mode_b is not None:
            self._away_state_b = (status.get(self.pyotgw.OTGW_GPIO_B_STATE) ==
                                  self._away_mode_b)
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the friendly name."""
        return self.friendly_name

    @property
    def precision(self):
        """Return the precision of the system."""
        if self.temp_precision is not None:
            return self.temp_precision
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def should_poll(self):
        """Disable polling for this entity."""
        return False

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
        return self._away_state_a or self._away_state_b

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temp = float(kwargs[ATTR_TEMPERATURE])
            self._target_temperature = await self.gateway.set_target_temp(
                temp)
            self.async_schedule_update_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 1

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30
