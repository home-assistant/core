"""Module contains the CompitClimate class for controlling climate entities."""

import asyncio
from typing import Any

from compit_inext_api import Device, Parameter

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANURFACER_NAME
from .coordinator import CompitDataUpdateCoordinator

PARAM_PRESET_MODE = "__trybpracytermostatu"
PARAM_FAN_MODE = "__trybaero"
PARAM_HVAC_MODE = "__trybpracyinstalacji"
PARAM_CURRENT_TEMPERATURE = "__tpokojowa"
PARAM_TARGET_TEMPERATURE = "__tpokzadana"
PARAM_SET_TARGET_TEMPERATURE = "__tempzadpracareczna"

type CompitConfigEntry = ConfigEntry[CompitDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the CompitClimate platform from a config entry."""

    coordinator: CompitDataUpdateCoordinator = entry.runtime_data

    async_add_devices(
        [
            CompitClimate(
                coordinator,
                device,
                device_definition.parameters,
                device_definition.name,
            )
            for gates in coordinator.gates
            for device in gates.devices
            if (
                device_definition := next(
                    (
                        definition
                        for definition in coordinator.device_definitions.devices
                        if definition.code == device.type
                    ),
                    None,
                )
            )
            is not None
            if (device_definition.device_class == 10)
        ]
    )


class CompitClimate(CoordinatorEntity[CompitDataUpdateCoordinator], ClimateEntity):
    """Representation of a Compit climate device."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device: Device,
        parameters: list[Parameter],
        device_name: str,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{device.label}_{device.id}"
        self._attr_name = device.label
        self._attr_has_entity_name = True
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
        )
        self._attr_device_info = DeviceInfo(
            {
                "identifiers": {(DOMAIN, str(device.id))},
                "name": device.label,
                "manufacturer": MANURFACER_NAME,
                "model": device_name,
                "sw_version": "1.0",
            }
        )

        parametersDict = {
            parameter.parameter_code: parameter for parameter in parameters
        }
        self.device = device
        self.available_presets: Parameter | None = parametersDict.get(PARAM_PRESET_MODE)
        self.available_fan_modes: Parameter | None = parametersDict.get(PARAM_FAN_MODE)
        self.available_hvac_modes: Parameter | None = parametersDict.get(
            PARAM_HVAC_MODE
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self.coordinator.data[self.device.id].state.get_parameter_value(
            PARAM_CURRENT_TEMPERATURE
        )
        if value is None:
            return None
        return float(value.value) if value is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        value = self.coordinator.data[self.device.id].state.get_parameter_value(
            PARAM_TARGET_TEMPERATURE
        )
        if value is None:
            return None
        return float(value.value) if value is not None else None

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the available preset modes."""
        if self.available_presets is None or self.available_presets.details is None:
            return []
        return [
            item.description
            for item in self.available_presets.details
            if item is not None
        ]

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the available fan modes."""
        if self.available_fan_modes is None or self.available_fan_modes.details is None:
            return []
        return [
            item.description
            for item in self.available_fan_modes.details
            if item is not None
        ]

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        preset_mode = self.coordinator.data[self.device.id].state.get_parameter_value(
            PARAM_PRESET_MODE
        )

        if (
            preset_mode is None
            or self.available_presets is None
            or self.available_presets.details is None
        ):
            return None

        val = next(
            (
                item
                for item in self.available_presets.details
                if item is not None and item.state == preset_mode.value
            ),
            None,
        )
        if val is None:
            return None
        return str(val.description)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self.coordinator.data[self.device.id].state.get_parameter_value(
            PARAM_FAN_MODE
        )
        if (
            fan_mode is None
            or self.available_fan_modes is None
            or self.available_fan_modes.details is None
        ):
            return None

        val = next(
            (
                item
                for item in self.available_fan_modes.details
                if item is not None and item.state == fan_mode.value
            ),
            None,
        )
        if val is None:
            return None
        return str(val.description)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        hvac_mode = self.coordinator.data[self.device.id].state.get_parameter_value(
            PARAM_HVAC_MODE
        )
        if hvac_mode:
            if hvac_mode.value == 0:
                return HVACMode.HEAT
            if hvac_mode.value == 1:
                return HVACMode.OFF
            if hvac_mode.value == 2:
                return HVACMode.COOL
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self.async_call_api(PARAM_SET_TARGET_TEMPERATURE, temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        value = 0
        if hvac_mode == HVACMode.HEAT:
            value = 0
        elif hvac_mode == HVACMode.OFF:
            value = 1
        elif hvac_mode == HVACMode.COOL:
            value = 2
        await self.async_call_api(PARAM_HVAC_MODE, value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if self.available_presets is None or self.available_presets.details is None:
            return
        value = next(
            (
                item
                for item in self.available_presets.details
                if item is not None and item.description == preset_mode
            ),
            None,
        )
        if value is None:
            return
        await self.async_call_api(PARAM_PRESET_MODE, value.state)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if self.available_fan_modes is None or self.available_fan_modes.details is None:
            return
        value = next(
            (
                item
                for item in self.available_fan_modes.details
                if item is not None and item.description == fan_mode
            ),
            None,
        )
        if value is None:
            return
        await self.async_call_api(PARAM_FAN_MODE, value.state)

    async def async_call_api(self, parameter: str, value: int) -> None:
        """Call the API to set a parameter to a new value."""

        if (
            await self.coordinator.api.update_device_parameter(
                self.device.id, parameter, value
            )
            is not False
        ):
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
