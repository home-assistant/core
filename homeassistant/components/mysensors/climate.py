"""MySensors platform that offers a Climate (MySensors-HVAC) component."""
from __future__ import annotations

from typing import Any

from homeassistant.components import mysensors
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.components.mysensors.const import MYSENSORS_DISCOVERY, DiscoveryInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .helpers import on_unload

DICT_HA_TO_MYS = {
    HVAC_MODE_AUTO: "AutoChangeOver",
    HVAC_MODE_COOL: "CoolOn",
    HVAC_MODE_HEAT: "HeatOn",
    HVAC_MODE_OFF: "Off",
}
DICT_MYS_TO_HA = {
    "AutoChangeOver": HVAC_MODE_AUTO,
    "CoolOn": HVAC_MODE_COOL,
    "HeatOn": HVAC_MODE_HEAT,
    "Off": HVAC_MODE_OFF,
}

FAN_LIST = ["Auto", "Min", "Normal", "Max"]
OPERATION_LIST = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_HEAT]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors climate."""
        mysensors.setup_mysensors_platform(
            hass,
            DOMAIN,
            discovery_info,
            MySensorsHVAC,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, DOMAIN),
            async_discover,
        ),
    )


class MySensorsHVAC(mysensors.device.MySensorsEntity, ClimateEntity):
    """Representation of a MySensors HVAC."""

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        features = 0
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SPEED in self._values:
            features = features | SUPPORT_FAN_MODE
        if (
            set_req.V_HVAC_SETPOINT_COOL in self._values
            and set_req.V_HVAC_SETPOINT_HEAT in self._values
        ):
            features = features | SUPPORT_TARGET_TEMPERATURE_RANGE
        else:
            features = features | SUPPORT_TARGET_TEMPERATURE
        return features

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS if self.hass.config.units.is_metric else TEMP_FAHRENHEIT

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
        """Return the temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if (
            set_req.V_HVAC_SETPOINT_COOL in self._values
            and set_req.V_HVAC_SETPOINT_HEAT in self._values
        ):
            return None
        temp = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
        if temp is None:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
        return float(temp) if temp is not None else None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_HEAT in self._values:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
            return float(temp) if temp is not None else None

        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_COOL in self._values:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
            return float(temp) if temp is not None else None

        return None

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        return self._values.get(self.value_type, HVAC_MODE_HEAT)

    @property
    def hvac_modes(self) -> list[str]:
        """List of available operation modes."""
        return OPERATION_LIST

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
            if self.assumed_state:
                # Optimistically assume that device has changed state
                self._values[value_type] = value
                self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_HVAC_SPEED, fan_mode, ack=1
        )
        if self.assumed_state:
            # Optimistically assume that device has changed state
            self._values[set_req.V_HVAC_SPEED] = fan_mode
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target temperature."""
        self.gateway.set_child_value(
            self.node_id,
            self.child_id,
            self.value_type,
            DICT_HA_TO_MYS[hvac_mode],
            ack=1,
        )
        if self.assumed_state:
            # Optimistically assume that device has changed state
            self._values[self.value_type] = hvac_mode
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the controller with the latest value from a sensor."""
        await super().async_update()
        self._values[self.value_type] = DICT_MYS_TO_HA[self._values[self.value_type]]
