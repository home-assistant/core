"""Climate platform for Poolside TEMPERATURE controls (heaters)."""

from typing import Any, override

from aiopoolside import PoolsideClient, PoolsideControl
from aiopoolside.const import (
    CONTROL_MODE_FIELD,
    CONTROL_MODES_SUPPORTED_FIELD,
    CURRENT_TEMPERATURE_FIELD,
    SET_POINT_FIELD,
    ControlMode,
    StatusState,
)

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PoolsideConfigEntry
from .entity import PoolsideEntity, control_platform

_HVAC_MODE_BY_CONTROL_MODE = {
    ControlMode.HEAT: HVACMode.HEAT,
    ControlMode.COOL: HVACMode.COOL,
    ControlMode.AUTO: HVACMode.HEAT_COOL,
}
_CONTROL_MODE_BY_HVAC_MODE = {v: k for k, v in _HVAC_MODE_BY_CONTROL_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Poolside climate entities."""
    data = entry.runtime_data
    async_add_entities(
        PoolsideThermostat(data.client, control)
        for control in data.controls
        if control_platform(control) is Platform.CLIMATE
    )


class PoolsideThermostat(PoolsideEntity, ClimateEntity):
    """A TEMPERATURE control exposed as a heater/chiller thermostat.

    TEMPERATURE has no ControlItemUUID of its own - it regulates the body of
    water, so confirmed status (current temperature, supported modes) is read
    via the group's BodyOfWaterUUID (`status_key`). On/off is resolved via
    `_power_state()` (ActualPowerState/PowerState if pushed, our own optimistic
    echo otherwise); SetPoint/ControlMode remain optimistic-only for now.
    """

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    # All temperatures on this wire are degrees Fahrenheit.
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the thermostat, applying the control's setpoint bounds if known."""
        super().__init__(client, control)
        if (min_set_point := control.min_set_point) is not None:
            self._attr_min_temp = min_set_point
        if (max_set_point := control.max_set_point) is not None:
            self._attr_max_temp = max_set_point

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the modes this body of water's installed equipment supports."""
        modes = [HVACMode.OFF]
        for raw_mode in self._confirmed_json_list(CONTROL_MODES_SUPPORTED_FIELD):
            try:
                modes.append(_HVAC_MODE_BY_CONTROL_MODE[ControlMode(raw_mode)])
            except ValueError:
                continue
        if len(modes) == 1:
            # Equipment capabilities haven't been confirmed yet; fall back to
            # HEAT so the entity has some way to be turned on.
            modes.append(HVACMode.HEAT)
        return modes

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the current operating mode."""
        if self._power_state() != StatusState.ON:
            return HVACMode.OFF
        try:
            return _HVAC_MODE_BY_CONTROL_MODE[
                ControlMode(self._desired(CONTROL_MODE_FIELD))
            ]
        except ValueError, KeyError:
            return HVACMode.HEAT

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the body of water's last reported temperature."""
        value = self._confirmed(CURRENT_TEMPERATURE_FIELD)
        return None if value is None else float(value)

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the heater's setpoint."""
        value = self._desired(SET_POINT_FIELD)
        return None if value is None else float(value)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the heater/chiller on or off, and select its control mode."""
        if hvac_mode == HVACMode.OFF:
            await self._async_write_state(Status=StatusState.OFF.value)
            return
        fields: dict[str, Any] = {"Status": StatusState.ON.value}
        if control_mode := _CONTROL_MODE_BY_HVAC_MODE.get(hvac_mode):
            fields[CONTROL_MODE_FIELD] = control_mode.value
        await self._async_write_state(**fields)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the heater's setpoint (an integer number of degrees Fahrenheit)."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._async_write_state(SetPoint=str(round(temperature)))
