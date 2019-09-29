"""Support for OpenTherm Gateway climate devices."""
import logging

from pyotgw import vars as gw_vars

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    PRESET_AWAY,
    SUPPORT_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_FLOOR_TEMP, CONF_PRECISION, DATA_GATEWAYS, DATA_OPENTHERM_GW


_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the opentherm_gw device."""
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][discovery_info]

    gateway = OpenThermClimate(gw_dev)
    async_add_entities([gateway])


class OpenThermClimate(ClimateDevice):
    """Representation of a climate device."""

    def __init__(self, gw_dev):
        """Initialize the device."""
        self._gateway = gw_dev
        self.friendly_name = gw_dev.name
        self.floor_temp = gw_dev.climate_config[CONF_FLOOR_TEMP]
        self.temp_precision = gw_dev.climate_config.get(CONF_PRECISION)
        self._current_operation = HVAC_MODE_OFF
        self._current_temperature = None
        self._new_target_temperature = None
        self._target_temperature = None
        self._away_mode_a = None
        self._away_mode_b = None
        self._away_state_a = False
        self._away_state_b = False

    async def async_added_to_hass(self):
        """Connect to the OpenTherm Gateway device."""
        _LOGGER.debug("Added device %s", self.friendly_name)
        async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    @callback
    def receive_report(self, status):
        """Receive and handle a new report from the Gateway."""
        ch_active = status.get(gw_vars.DATA_SLAVE_CH_ACTIVE)
        flame_on = status.get(gw_vars.DATA_SLAVE_FLAME_ON)
        cooling_active = status.get(gw_vars.DATA_SLAVE_COOLING_ACTIVE)
        if ch_active and flame_on:
            self._current_operation = HVAC_MODE_HEAT
        elif cooling_active:
            self._current_operation = HVAC_MODE_COOL
        else:
            self._current_operation = HVAC_MODE_OFF

        self._current_temperature = status.get(gw_vars.DATA_ROOM_TEMP)
        temp_upd = status.get(gw_vars.DATA_ROOM_SETPOINT)

        if self._target_temperature != temp_upd:
            self._new_target_temperature = None
        self._target_temperature = temp_upd

        # GPIO mode 5: 0 == Away
        # GPIO mode 6: 1 == Away
        gpio_a_state = status.get(gw_vars.OTGW_GPIO_A)
        if gpio_a_state == 5:
            self._away_mode_a = 0
        elif gpio_a_state == 6:
            self._away_mode_a = 1
        else:
            self._away_mode_a = None
        gpio_b_state = status.get(gw_vars.OTGW_GPIO_B)
        if gpio_b_state == 5:
            self._away_mode_b = 0
        elif gpio_b_state == 6:
            self._away_mode_b = 1
        else:
            self._away_mode_b = None
        if self._away_mode_a is not None:
            self._away_state_a = (
                status.get(gw_vars.OTGW_GPIO_A_STATE) == self._away_mode_a
            )
        if self._away_mode_b is not None:
            self._away_state_b = (
                status.get(gw_vars.OTGW_GPIO_B_STATE) == self._away_mode_b
            )
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the friendly name."""
        return self.friendly_name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._gateway.gw_id

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
    def hvac_mode(self):
        """Return current HVAC mode."""
        return self._current_operation

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return []

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._current_temperature is None:
            return
        if self.floor_temp is True:
            if self.precision == PRECISION_HALVES:
                return int(2 * self._current_temperature) / 2
            if self.precision == PRECISION_TENTHS:
                return int(10 * self._current_temperature) / 10
            return int(self._current_temperature)
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._new_target_temperature or self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.precision

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self._away_state_a or self._away_state_b:
            return PRESET_AWAY

    @property
    def preset_modes(self):
        """Available preset modes to set."""
        return []

    def set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        _LOGGER.warning("Changing preset mode is not supported")

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temp = float(kwargs[ATTR_TEMPERATURE])
            if temp == self.target_temperature:
                return
            self._new_target_temperature = await self._gateway.gateway.set_target_temp(
                temp
            )
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
