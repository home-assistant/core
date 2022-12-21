"""Support for Rheem EcoNet thermostats."""
from typing import Any

from pyeconet.equipment import EquipmentType
from pyeconet.equipment.thermostat import ThermostatFanMode, ThermostatOperationMode

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

ECONET_STATE_TO_HA = {
    ThermostatOperationMode.HEATING: HVACMode.HEAT,
    ThermostatOperationMode.COOLING: HVACMode.COOL,
    ThermostatOperationMode.OFF: HVACMode.OFF,
    ThermostatOperationMode.AUTO: HVACMode.HEAT_COOL,
    ThermostatOperationMode.FAN_ONLY: HVACMode.FAN_ONLY,
}
HA_STATE_TO_ECONET = {value: key for key, value in ECONET_STATE_TO_HA.items()}

ECONET_FAN_STATE_TO_HA = {
    ThermostatFanMode.AUTO: FAN_AUTO,
    ThermostatFanMode.LOW: FAN_LOW,
    ThermostatFanMode.MEDIUM: FAN_MEDIUM,
    ThermostatFanMode.HIGH: FAN_HIGH,
}
HA_FAN_STATE_TO_ECONET = {value: key for key, value in ECONET_FAN_STATE_TO_HA.items()}

SUPPORT_FLAGS_THERMOSTAT = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.AUX_HEAT
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EcoNet thermostat based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    async_add_entities(
        [
            EcoNetThermostat(thermostat)
            for thermostat in equipment[EquipmentType.THERMOSTAT]
        ],
    )


class EcoNetThermostat(EcoNetEntity, ClimateEntity):
    """Define a Econet thermostat."""

    def __init__(self, thermostat):
        """Initialize."""
        super().__init__(thermostat)
        self._running = thermostat.running
        self._poll = True
        self.econet_state_to_ha = {}
        self.ha_state_to_econet = {}
        self.op_list = []
        for mode in self._econet.modes:
            if mode not in [
                ThermostatOperationMode.UNKNOWN,
                ThermostatOperationMode.EMERGENCY_HEAT,
            ]:
                ha_mode = ECONET_STATE_TO_HA[mode]
                self.op_list.append(ha_mode)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        if self._econet.supports_humidifier:
            return SUPPORT_FLAGS_THERMOSTAT | ClimateEntityFeature.TARGET_HUMIDITY
        return SUPPORT_FLAGS_THERMOSTAT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._econet.set_point

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._econet.humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        if self._econet.supports_humidifier:
            return self._econet.dehumidifier_set_point
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.COOL:
            return self._econet.cool_set_point
        if self.hvac_mode == HVACMode.HEAT:
            return self._econet.heat_set_point
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._econet.heat_set_point
        return None

    @property
    def target_temperature_high(self):
        """Return the higher bound temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._econet.cool_set_point
        return None

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp:
            self._econet.set_set_point(target_temp, None, None)
        if target_temp_low or target_temp_high:
            self._econet.set_set_point(None, target_temp_high, target_temp_low)

    @property
    def is_aux_heat(self):
        """Return true if aux heater."""
        return self._econet.mode == ThermostatOperationMode.EMERGENCY_HEAT

    @property
    def hvac_modes(self):
        """Return hvac operation ie. heat, cool mode.

        Needs to be one of HVAC_MODE_*.
        """
        return self.op_list

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool, mode.

        Needs to be one of HVAC_MODE_*.
        """
        econet_mode = self._econet.mode
        _current_op = HVACMode.OFF
        if econet_mode is not None:
            _current_op = ECONET_STATE_TO_HA[econet_mode]

        return _current_op

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        hvac_mode_to_set = HA_STATE_TO_ECONET.get(hvac_mode)
        if hvac_mode_to_set is None:
            raise ValueError(f"{hvac_mode} is not a valid mode.")
        self._econet.set_mode(hvac_mode_to_set)

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        self._econet.set_dehumidifier_set_point(humidity)

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        econet_fan_mode = self._econet.fan_mode

        # Remove this after we figure out how to handle med lo and med hi
        if econet_fan_mode in [ThermostatFanMode.MEDHI, ThermostatFanMode.MEDLO]:
            econet_fan_mode = ThermostatFanMode.MEDIUM

        _current_fan_mode = FAN_AUTO
        if econet_fan_mode is not None:
            _current_fan_mode = ECONET_FAN_STATE_TO_HA[econet_fan_mode]
        return _current_fan_mode

    @property
    def fan_modes(self):
        """Return the fan modes."""
        econet_fan_modes = self._econet.fan_modes
        fan_list = []
        for mode in econet_fan_modes:
            # Remove the MEDLO MEDHI once we figure out how to handle it
            if mode not in [
                ThermostatFanMode.UNKNOWN,
                ThermostatFanMode.MEDLO,
                ThermostatFanMode.MEDHI,
            ]:
                fan_list.append(ECONET_FAN_STATE_TO_HA[mode])
        return fan_list

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        self._econet.set_fan_mode(HA_FAN_STATE_TO_ECONET[fan_mode])

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        self._econet.set_mode(ThermostatOperationMode.EMERGENCY_HEAT)

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        self._econet.set_mode(ThermostatOperationMode.HEATING)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._econet.set_point_limits[0]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._econet.set_point_limits[1]

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self._econet.dehumidifier_set_point_limits[0]

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self._econet.dehumidifier_set_point_limits[1]
