"""Module contains the CompitClimate class for controlling climate entities."""

import logging
from typing import Any

from compit_inext_api import Param, Parameter
from compit_inext_api.consts import (
    CompitFanMode,
    CompitHVACMode,
    CompitParameter,
    CompitPresetMode,
)
from propcache.api import cached_property

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Device class for climate devices in Compit system
CLIMATE_DEVICE_CLASS = 10
PARALLEL_UPDATES = 0

COMPIT_MODE_MAP = {
    CompitHVACMode.COOL: HVACMode.COOL,
    CompitHVACMode.HEAT: HVACMode.HEAT,
    CompitHVACMode.OFF: HVACMode.OFF,
}

COMPIT_FANSPEED_MAP = {
    CompitFanMode.OFF: FAN_OFF,
    CompitFanMode.AUTO: FAN_AUTO,
    CompitFanMode.LOW: FAN_LOW,
    CompitFanMode.MEDIUM: FAN_MEDIUM,
    CompitFanMode.HIGH: FAN_HIGH,
    CompitFanMode.HOLIDAY: FAN_AUTO,
}

COMPIT_PRESET_MAP = {
    CompitPresetMode.AUTO: PRESET_HOME,
    CompitPresetMode.HOLIDAY: PRESET_ECO,
    CompitPresetMode.MANUAL: PRESET_NONE,
    CompitPresetMode.AWAY: PRESET_AWAY,
}

HVAC_MODE_TO_COMPIT_MODE = {v: k for k, v in COMPIT_MODE_MAP.items()}
FAN_MODE_TO_COMPIT_FAN_MODE = {v: k for k, v in COMPIT_FANSPEED_MAP.items()}
PRESET_MODE_TO_COMPIT_PRESET_MODE = {v: k for k, v in COMPIT_PRESET_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the CompitClimate platform from a config entry."""

    coordinator = entry.runtime_data
    climate_entities = []
    for device_id in coordinator.connector.all_devices:
        device = coordinator.connector.all_devices[device_id]

        if device.definition.device_class == CLIMATE_DEVICE_CLASS:
            climate_entities.append(
                CompitClimate(
                    coordinator,
                    device_id,
                    {
                        parameter.parameter_code: parameter
                        for parameter in device.definition.parameters
                    },
                    device.definition.name,
                )
            )

    async_add_devices(climate_entities)


class CompitClimate(CoordinatorEntity[CompitDataUpdateCoordinator], ClimateEntity):
    """Representation of a Compit climate device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [*COMPIT_MODE_MAP.values()]
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
        device_id: int,
        parameters: dict[str, Parameter],
        device_name: str,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_name}_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
        )

        self.parameters = parameters
        self.device_id = device_id
        self.available_presets: Parameter | None = self.parameters.get(
            CompitParameter.PRESET_MODE.value
        )
        self.available_fan_modes: Parameter | None = self.parameters.get(
            CompitParameter.FAN_MODE.value
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.device_id in self.coordinator.connector.all_devices
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self.get_parameter_value(CompitParameter.CURRENT_TEMPERATURE)
        if value is None:
            return None
        return float(value.value)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        value = self.get_parameter_value(CompitParameter.SET_TARGET_TEMPERATURE)
        if value is None:
            return None
        return float(value.value)

    @cached_property
    def preset_modes(self) -> list[str] | None:
        """Return the available preset modes."""
        if self.available_presets is None or self.available_presets.details is None:
            return []

        preset_modes = []
        for item in self.available_presets.details:
            if item is not None:
                ha_preset = COMPIT_PRESET_MAP.get(CompitPresetMode(item.state))
                if ha_preset and ha_preset not in preset_modes:
                    preset_modes.append(ha_preset)

        return preset_modes

    @cached_property
    def fan_modes(self) -> list[str] | None:
        """Return the available fan modes."""
        if self.available_fan_modes is None or self.available_fan_modes.details is None:
            return []

        fan_modes = []
        for item in self.available_fan_modes.details:
            if item is not None:
                ha_fan_mode = COMPIT_FANSPEED_MAP.get(CompitFanMode(item.state))
                if ha_fan_mode and ha_fan_mode not in fan_modes:
                    fan_modes.append(ha_fan_mode)

        return fan_modes

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        preset_mode = self.get_parameter_value(CompitParameter.PRESET_MODE)

        if preset_mode:
            compit_preset_mode = CompitPresetMode(preset_mode.value)
            return COMPIT_PRESET_MAP.get(compit_preset_mode)
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self.get_parameter_value(CompitParameter.FAN_MODE)
        if fan_mode:
            compit_fan_mode = CompitFanMode(fan_mode.value)
            return COMPIT_FANSPEED_MAP.get(compit_fan_mode)
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        hvac_mode = self.get_parameter_value(CompitParameter.HVAC_MODE)
        if hvac_mode:
            compit_hvac_mode = CompitHVACMode(hvac_mode.value)
            return COMPIT_MODE_MAP.get(compit_hvac_mode)
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            raise ServiceValidationError("Temperature argument missing")
        await self.set_parameter_value(CompitParameter.SET_TARGET_TEMPERATURE, temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""

        if not (mode := HVAC_MODE_TO_COMPIT_MODE.get(hvac_mode)):
            raise ServiceValidationError(f"Invalid hvac mode {hvac_mode}")

        await self.set_parameter_value(CompitParameter.HVAC_MODE, mode.value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""

        compit_preset = PRESET_MODE_TO_COMPIT_PRESET_MODE.get(preset_mode)
        if compit_preset is None:
            raise ServiceValidationError(f"Invalid preset mode: {preset_mode}")

        await self.set_parameter_value(CompitParameter.PRESET_MODE, compit_preset.value)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""

        compit_fan_mode = FAN_MODE_TO_COMPIT_FAN_MODE.get(fan_mode)
        if compit_fan_mode is None:
            raise ServiceValidationError(f"Invalid fan mode: {fan_mode}")

        await self.set_parameter_value(CompitParameter.FAN_MODE, compit_fan_mode.value)

    async def set_parameter_value(self, parameter: CompitParameter, value: int) -> None:
        """Call the API to set a parameter to a new value."""
        await self.coordinator.connector.set_device_parameter(
            self.device_id, parameter, value
        )
        self.async_write_ha_state()

    def get_parameter_value(self, parameter: CompitParameter) -> Param | None:
        """Get the parameter value from the device state."""
        return self.coordinator.connector.get_device_parameter(
            self.device_id, parameter
        )
