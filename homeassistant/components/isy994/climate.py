"""Support for Insteon Thermostats via ISY Platform."""
from __future__ import annotations

from typing import Any

from pyisy.constants import (
    CMD_CLIMATE_FAN_SETTING,
    CMD_CLIMATE_MODE,
    ISY_VALUE_UNKNOWN,
    PROP_HEAT_COOL_STATE,
    PROP_HUMIDITY,
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROP_UOM,
    PROTO_INSTEON,
)
from pyisy.nodes import Node

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_OFF,
    FAN_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .const import (
    _LOGGER,
    DOMAIN,
    HA_FAN_TO_ISY,
    HA_HVAC_TO_ISY,
    ISY_HVAC_MODES,
    UOM_FAN_MODES,
    UOM_HVAC_ACTIONS,
    UOM_HVAC_MODE_GENERIC,
    UOM_HVAC_MODE_INSTEON,
    UOM_ISY_CELSIUS,
    UOM_ISY_FAHRENHEIT,
    UOM_ISYV4_NONE,
    UOM_TO_STATES,
)
from .entity import ISYNodeEntity
from .helpers import convert_isy_value_to_hass


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY thermostat platform."""
    entities = []

    isy_data = hass.data[DOMAIN][entry.entry_id]
    devices: dict[str, DeviceInfo] = isy_data.devices
    for node in isy_data.nodes[Platform.CLIMATE]:
        entities.append(ISYThermostatEntity(node, devices.get(node.primary_node)))

    async_add_entities(entities)


class ISYThermostatEntity(ISYNodeEntity, ClimateEntity):
    """Representation of an ISY thermostat entity."""

    _attr_hvac_modes = ISY_HVAC_MODES
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )

    def __init__(self, node: Node, device_info: DeviceInfo | None = None) -> None:
        """Initialize the ISY Thermostat entity."""
        super().__init__(node, device_info=device_info)
        self._uom = self._node.uom
        if isinstance(self._uom, list):
            self._uom = self._node.uom[0]
        self._hvac_action: str | None = None
        self._hvac_mode: str | None = None
        self._fan_mode: str | None = None
        self._temp_unit = None
        self._current_humidity = 0
        self._target_temp_low = 0
        self._target_temp_high = 0

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if not (uom := self._node.aux_properties.get(PROP_UOM)):
            return self.hass.config.units.temperature_unit
        if uom.value == UOM_ISY_CELSIUS:
            return UnitOfTemperature.CELSIUS
        if uom.value == UOM_ISY_FAHRENHEIT:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        if not (humidity := self._node.aux_properties.get(PROP_HUMIDITY)):
            return None
        if humidity.value == ISY_VALUE_UNKNOWN:
            return None
        return int(humidity.value)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if not (hvac_mode := self._node.aux_properties.get(CMD_CLIMATE_MODE)):
            return HVACMode.OFF

        # Which state values used depends on the mode property's UOM:
        uom = hvac_mode.uom
        # Handle special case for ISYv4 Firmware:
        if uom in (UOM_ISYV4_NONE, ""):
            uom = (
                UOM_HVAC_MODE_INSTEON
                if self._node.protocol == PROTO_INSTEON
                else UOM_HVAC_MODE_GENERIC
            )
        return (
            try_parse_enum(HVACMode, UOM_TO_STATES[uom].get(hvac_mode.value))
            or HVACMode.OFF
        )

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        hvac_action = self._node.aux_properties.get(PROP_HEAT_COOL_STATE)
        if not hvac_action:
            return None
        return try_parse_enum(
            HVACAction, UOM_TO_STATES[UOM_HVAC_ACTIONS].get(hvac_action.value)
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return convert_isy_value_to_hass(
            self._node.status, self._uom, self._node.prec, 1
        )

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return 1.0

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.COOL:
            return self.target_temperature_high
        if self.hvac_mode == HVACMode.HEAT:
            return self.target_temperature_low
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        target = self._node.aux_properties.get(PROP_SETPOINT_COOL)
        if not target:
            return None
        return convert_isy_value_to_hass(target.value, target.uom, target.prec, 1)

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        target = self._node.aux_properties.get(PROP_SETPOINT_HEAT)
        if not target:
            return None
        return convert_isy_value_to_hass(target.value, target.uom, target.prec, 1)

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return [FAN_AUTO, FAN_ON]

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode ie. auto, on."""
        fan_mode = self._node.aux_properties.get(CMD_CLIMATE_FAN_SETTING)
        if not fan_mode:
            return FAN_OFF
        return UOM_TO_STATES[UOM_FAN_MODES].get(fan_mode.value, FAN_OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp is not None:
            if self.hvac_mode == HVACMode.COOL:
                target_temp_high = target_temp
            if self.hvac_mode == HVACMode.HEAT:
                target_temp_low = target_temp
        if target_temp_low is not None:
            await self._node.set_climate_setpoint_heat(int(target_temp_low))
            # Presumptive setting--event stream will correct if cmd fails:
            self._target_temp_low = target_temp_low
        if target_temp_high is not None:
            await self._node.set_climate_setpoint_cool(int(target_temp_high))
            # Presumptive setting--event stream will correct if cmd fails:
            self._target_temp_high = target_temp_high
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        _LOGGER.debug("Requested fan mode %s", fan_mode)
        await self._node.set_fan_mode(HA_FAN_TO_ISY.get(fan_mode))
        # Presumptive setting--event stream will correct if cmd fails:
        self._fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug("Requested operation mode %s", hvac_mode)
        await self._node.set_climate_mode(HA_HVAC_TO_ISY.get(hvac_mode))
        # Presumptive setting--event stream will correct if cmd fails:
        self._hvac_mode = hvac_mode
        self.async_write_ha_state()
