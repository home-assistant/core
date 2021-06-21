"""Support for Wink water heaters."""
import logging

import pywink

from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import STATE_OFF, STATE_UNKNOWN, TEMP_CELSIUS

from . import DOMAIN, WinkDevice

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS_HEATER = (
    SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE
)

ATTR_RHEEM_TYPE = "rheem_type"
ATTR_VACATION_MODE = "vacation_mode"

HA_STATE_TO_WINK = {
    STATE_ECO: "eco",
    STATE_ELECTRIC: "electric_only",
    STATE_GAS: "gas",
    STATE_HEAT_PUMP: "heat_pump",
    STATE_HIGH_DEMAND: "high_demand",
    STATE_OFF: "off",
    STATE_PERFORMANCE: "performance",
}

WINK_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_WINK.items()}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink water heater devices."""

    for water_heater in pywink.get_water_heaters():
        _id = water_heater.object_id() + water_heater.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkWaterHeater(water_heater, hass)])


class WinkWaterHeater(WinkDevice, WaterHeaterEntity):
    """Representation of a Wink water heater."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        # The Wink API always returns temp in Celsius
        return TEMP_CELSIUS

    @property
    def extra_state_attributes(self):
        """Return the optional device state attributes."""
        data = {}
        data[ATTR_VACATION_MODE] = self.wink.vacation_mode_enabled()
        data[ATTR_RHEEM_TYPE] = self.wink.rheem_type()

        return data

    @property
    def current_operation(self):
        """
        Return current operation one of the following.

        ["eco", "performance", "heat_pump",
        "high_demand", "electric_only", "gas]
        """
        if not self.wink.is_on():
            current_op = STATE_OFF
        else:
            current_op = WINK_STATE_TO_HA.get(self.wink.current_mode())
            if current_op is None:
                current_op = STATE_UNKNOWN
        return current_op

    @property
    def operation_list(self):
        """List of available operation modes."""
        op_list = ["off"]
        modes = self.wink.modes()
        for mode in modes:
            if mode == "aux":
                continue
            ha_mode = WINK_STATE_TO_HA.get(mode)
            if ha_mode is not None:
                op_list.append(ha_mode)
            else:
                error = (
                    "Invalid operation mode mapping. "
                    f"{mode} doesn't map. Please report this."
                )
                _LOGGER.error(error)
        return op_list

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        self.wink.set_temperature(target_temp)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        op_mode_to_set = HA_STATE_TO_WINK.get(operation_mode)
        self.wink.set_operation_mode(op_mode_to_set)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.wink.current_set_point()

    def turn_away_mode_on(self):
        """Turn away on."""
        self.wink.set_vacation_mode(True)

    def turn_away_mode_off(self):
        """Turn away off."""
        self.wink.set_vacation_mode(False)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.wink.min_set_point()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.wink.max_set_point()
