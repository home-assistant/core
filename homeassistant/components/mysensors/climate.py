"""MySensors platform that offers a Climate (MySensors-HVAC) component."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import setup_mysensors_platform
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .entity import MySensorsChildEntity

DICT_HA_TO_MYS = {
    HVACMode.AUTO: "AutoChangeOver",
    HVACMode.COOL: "CoolOn",
    HVACMode.HEAT: "HeatOn",
    HVACMode.OFF: "Off",
}
DICT_MYS_TO_HA = {
    "AutoChangeOver": HVACMode.AUTO,
    "CoolOn": HVACMode.COOL,
    "HeatOn": HVACMode.HEAT,
    "Off": HVACMode.OFF,
}

FAN_LIST = ["Auto", "Min", "Normal", "Max"]
OPERATION_LIST = [HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors climate."""
        setup_mysensors_platform(
            hass,
            Platform.CLIMATE,
            discovery_info,
            MySensorsHVAC,
            async_add_entities=async_add_entities,
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.CLIMATE),
            async_discover,
        ),
    )


class MySensorsHVAC(MySensorsChildEntity, ClimateEntity):
    """Representation of a MySensors HVAC."""

    _attr_hvac_modes = OPERATION_LIST

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SPEED in self._values:
            features = features | ClimateEntityFeature.FAN_MODE
        if (
            set_req.V_HVAC_SETPOINT_COOL in self._values
            and set_req.V_HVAC_SETPOINT_HEAT in self._values
        ):
            features = features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        elif (
            set_req.V_HVAC_SETPOINT_COOL in self._values
            or set_req.V_HVAC_SETPOINT_HEAT in self._values
        ):
            features = features | ClimateEntityFeature.TARGET_TEMPERATURE
        return features

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return (
            UnitOfTemperature.CELSIUS
            if self.hass.config.units is METRIC_SYSTEM
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value: str | None = self._values.get(self.gateway.const.SetReq.V_TEMP)
        float_value: float | None = None

        if value is not None:
            float_value = float(value)

        return float_value

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach.

        Either V_HVAC_SETPOINT_COOL or V_HVAC_SETPOINT_HEAT may be used.
        """
        set_req = self.gateway.const.SetReq
        temp = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
        if temp is None:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
        return float(temp) if temp is not None else None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        return float(self._values[set_req.V_HVAC_SETPOINT_COOL])

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        return float(self._values[set_req.V_HVAC_SETPOINT_HEAT])

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        return self._values.get(self.value_type, HVACMode.HEAT)  # type: ignore[no-any-return]

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._values.get(self.gateway.const.SetReq.V_HVAC_SPEED)

    @property
    def fan_modes(self) -> list[str]:
        """List of available fan modes."""
        return FAN_LIST

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        temp = kwargs.get(ATTR_TEMPERATURE)
        low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        heat = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
        cool = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
        updates = []
        if temp is not None:
            if heat is not None:
                # Set HEAT Target temperature
                value_type = set_req.V_HVAC_SETPOINT_HEAT
            elif cool is not None:
                # Set COOL Target temperature
                value_type = set_req.V_HVAC_SETPOINT_COOL
            if heat is not None or cool is not None:
                updates = [(value_type, temp)]
        elif all(val is not None for val in (low, high, heat, cool)):
            updates = [
                (set_req.V_HVAC_SETPOINT_HEAT, low),
                (set_req.V_HVAC_SETPOINT_COOL, high),
            ]
        for value_type, value in updates:
            self.gateway.set_child_value(
                self.node_id, self.child_id, value_type, value, ack=1
            )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_HVAC_SPEED, fan_mode, ack=1
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target temperature."""
        self.gateway.set_child_value(
            self.node_id,
            self.child_id,
            self.value_type,
            DICT_HA_TO_MYS[hvac_mode],
            ack=1,
        )

    @callback
    def _async_update(self) -> None:
        """Update the controller with the latest value from a sensor."""
        super()._async_update()
        self._values[self.value_type] = DICT_MYS_TO_HA[self._values[self.value_type]]
