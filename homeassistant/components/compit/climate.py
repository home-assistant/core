"""Module contains the CompitClimate class for controlling climate entities."""

import logging
from typing import Any

from compit_inext_api import Device, Parameter
from propcache import cached_property

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
from .enums import CompitHVACMode

_LOGGER: logging.Logger = logging.getLogger(__package__)
ATTR_TEMPERATURE = "temperature"
PARAM_PRESET_MODE = "__trybpracytermostatu"
PARAM_FAN_MODE = "__trybaero"
PARAM_HVAC_MODE = "__trybpracyinstalacji"
PARAM_CURRENT_TEMPERATURE = "__tpokojowa"
PARAM_TARGET_TEMPERATURE = "__tpokzadana"
PARAM_SET_TARGET_TEMPERATURE = "__tempzadpracareczna"
CLIMATE_DEVICE_CLASS = 10

COMPIT_MODE_MAP = {
    CompitHVACMode.COOL: HVACMode.COOL,
    CompitHVACMode.HEAT: HVACMode.HEAT,
    CompitHVACMode.OFF: HVACMode.OFF,
}

HVAC_MODE_TO_COMCOMPIT_MODE = {v: k for k, v in COMPIT_MODE_MAP.items()}

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
            if (device_definition.device_class == CLIMATE_DEVICE_CLASS)
        ]
    )


class CompitClimate(CoordinatorEntity[CompitDataUpdateCoordinator], ClimateEntity):
    """Representation of a Compit climate device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    _attr_name = None
    _attr_has_entity_name = True
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device: Device,
        parameters: list[Parameter],
        device_name: str,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.label}_{device.id}"
        self._attr_device_info = DeviceInfo(
            {
                "identifiers": {(DOMAIN, str(device.id))},
                "name": device.label,
                "manufacturer": MANURFACER_NAME,
                "model": device_name,
            }
        )

        parametersDict = {
            parameter.parameter_code: parameter for parameter in parameters
        }
        self.device_id = device.id
        self.available_presets: Parameter | None = parametersDict.get(PARAM_PRESET_MODE)
        self.available_fan_modes: Parameter | None = parametersDict.get(PARAM_FAN_MODE)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self.get_parameter_value(PARAM_CURRENT_TEMPERATURE)
        if value is None:
            _LOGGER.warning("current_temperature is None")
            return None
        return float(value.value)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        value = self.get_parameter_value(PARAM_TARGET_TEMPERATURE)
        if value is None:
            _LOGGER.warning("target_temperature is None")
            return None
        return float(value.value)

    @cached_property
    def preset_modes(self) -> list[str] | None:
        """Return the available preset modes."""
        if self.available_presets is None or self.available_presets.details is None:
            return []
        return [
            item.description
            for item in self.available_presets.details
            if item is not None
        ]

    @cached_property
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
        preset_mode = self.get_parameter_value(PARAM_PRESET_MODE)

        if preset_mode is None:
            return None
        if self.available_presets is None or self.available_presets.details is None:
            _LOGGER.warning("available_presets is None")
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
            _LOGGER.warning("Current preset mode not found in available presets")
            return None
        return val.description

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self.get_parameter_value(PARAM_FAN_MODE)
        if fan_mode is None:
            return None

        if self.available_fan_modes is None or self.available_fan_modes.details is None:
            _LOGGER.warning("available_fan_modes is None")
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
            _LOGGER.warning("Current fan mode not found in available fan modes")
            return None
        return val.description

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        hvac_mode = self.get_parameter_value(PARAM_HVAC_MODE)
        if hvac_mode:
            return COMPIT_MODE_MAP.get(hvac_mode.value)
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            raise ValueError("Temperature argument missing")
        await self.async_call_api(PARAM_SET_TARGET_TEMPERATURE, temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""

        if not (mode := HVAC_MODE_TO_COMCOMPIT_MODE.get(hvac_mode)):
            raise ValueError(f"Invalid hvac mode {hvac_mode}")

        await self.async_call_api(PARAM_HVAC_MODE, mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if self.available_presets is None or self.available_presets.details is None:
            _LOGGER.debug("available_presets is None")
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
            raise ValueError("Invalid preset mode")
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
            raise ValueError("Invalid fan mode")
        await self.async_call_api(PARAM_FAN_MODE, value.state)

    async def async_call_api(self, parameter: str, value: int) -> None:
        """Call the API to set a parameter to a new value."""

        if (
            await self.coordinator.api.update_device_parameter(
                self.device_id, parameter, value
            )
            is not False
        ):
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()

    def get_parameter_value(self, value):
        """Get the parameter value from the device state."""
        return self.coordinator.data[self.device_id].state.get_parameter_value(value)
