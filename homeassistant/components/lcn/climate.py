"""Support for LCN climate control."""

import pypck

from homeassistant.components.climate import ClimateEntity, const
from homeassistant.const import ATTR_TEMPERATURE, CONF_ADDRESS, CONF_UNIT_OF_MEASUREMENT

from . import LcnEntity
from .const import (
    CONF_CONNECTIONS,
    CONF_LOCKABLE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SETPOINT,
    CONF_SOURCE,
    DATA_LCN,
)
from .helpers import get_connection

PARALLEL_UPDATES = 0


async def async_setup_platform(
    hass, hass_config, async_add_entities, discovery_info=None
):
    """Set up the LCN climate platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        devices.append(LcnClimate(config, address_connection))

    async_add_entities(devices)


class LcnClimate(LcnEntity, ClimateEntity):
    """Representation of a LCN climate device."""

    def __init__(self, config, device_connection):
        """Initialize of a LCN climate device."""
        super().__init__(config, device_connection)

        self.variable = pypck.lcn_defs.Var[config[CONF_SOURCE]]
        self.setpoint = pypck.lcn_defs.Var[config[CONF_SETPOINT]]
        self.unit = pypck.lcn_defs.VarUnit.parse(config[CONF_UNIT_OF_MEASUREMENT])

        self.regulator_id = pypck.lcn_defs.Var.to_set_point_id(self.setpoint)
        self.is_lockable = config[CONF_LOCKABLE]
        self._max_temp = config[CONF_MAX_TEMP]
        self._min_temp = config[CONF_MIN_TEMP]

        self._current_temperature = None
        self._target_temperature = None
        self._is_on = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.device_connection.activate_status_request_handler(self.variable)
        await self.device_connection.activate_status_request_handler(self.setpoint)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return const.SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.unit.value

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._is_on:
            return const.HVAC_MODE_HEAT
        return const.HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        modes = [const.HVAC_MODE_HEAT]
        if self.is_lockable:
            modes.append(const.HVAC_MODE_OFF)
        return modes

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == const.HVAC_MODE_HEAT:
            if not await self.device_connection.lock_regulator(
                self.regulator_id, False
            ):
                return
            self._is_on = True
            self.async_write_ha_state()
        elif hvac_mode == const.HVAC_MODE_OFF:
            if not await self.device_connection.lock_regulator(self.regulator_id, True):
                return
            self._is_on = False
            self._target_temperature = None
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if not await self.device_connection.var_abs(
            self.setpoint, temperature, self.unit
        ):
            return
        self._target_temperature = temperature
        self.async_write_ha_state()

    def input_received(self, input_obj):
        """Set temperature value when LCN input object is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusVar):
            return

        if input_obj.get_var() == self.variable:
            self._current_temperature = input_obj.get_value().to_var_unit(self.unit)
        elif input_obj.get_var() == self.setpoint:
            self._is_on = not input_obj.get_value().is_locked_regulator()
            if self._is_on:
                self._target_temperature = input_obj.get_value().to_var_unit(self.unit)

        self.async_write_ha_state()
