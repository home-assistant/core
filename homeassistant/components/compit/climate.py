"""Module contains the CompitClimate class for controlling climate entities."""

from dataclasses import dataclass
import logging
from typing import Any, override

from compit_inext_api.consts import (
    CompitFanMode,
    CompitHVACMode,
    CompitParameter,
    CompitPresetMode,
)

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
    ClimateEntityDescription,
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

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CompitDeviceDescription(ClimateEntityDescription):
    """Class to describe a Compit climate entity."""

    supported_features: ClimateEntityFeature
    available_presets: list[str]
    available_fan_modes: list[str]
    available_hvac_modes: list[HVACMode]


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

DEVICE_DEFINITIONS: dict[int, CompitDeviceDescription] = {
    224: CompitDeviceDescription(
        key="R 900",
        supported_features=ClimateEntityFeature.PRESET_MODE,
        available_presets=[PRESET_HOME, PRESET_AWAY],
        available_fan_modes=[],
        available_hvac_modes=[HVACMode.HEAT, HVACMode.OFF],
    ),
    223: CompitDeviceDescription(
        key="Nano Color 2",
        supported_features=ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        available_presets=[PRESET_HOME, PRESET_ECO, PRESET_NONE, PRESET_AWAY],
        available_fan_modes=[FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        available_hvac_modes=[
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.OFF,
        ],
    ),
    12: CompitDeviceDescription(
        key="Nano Color",
        supported_features=ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        available_presets=[PRESET_HOME, PRESET_ECO, PRESET_NONE, PRESET_AWAY],
        available_fan_modes=[FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        available_hvac_modes=[
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.OFF,
        ],
    ),
    7: CompitDeviceDescription(
        key="Nano One",
        supported_features=ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE,
        available_presets=[PRESET_HOME, PRESET_ECO, PRESET_NONE, PRESET_AWAY],
        available_fan_modes=[FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        available_hvac_modes=[
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.OFF,
        ],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the CompitClimate platform from a config entry."""

    coordinator = entry.runtime_data
    async_add_devices(
        CompitClimate(
            coordinator,
            device_id,
            device_definition,
        )
        for device_id, device in coordinator.connector.all_devices.items()
        if (device_definition := DEVICE_DEFINITIONS.get(device.definition.code))
    )


class CompitClimate(CoordinatorEntity[CompitDataUpdateCoordinator], ClimateEntity):
    """Representation of a Compit climate device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_name = None
    _attr_has_entity_name = True
    entity_description: CompitDeviceDescription

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        entity_description: CompitDeviceDescription,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entity_description.key}_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=entity_description.key,
            manufacturer=MANUFACTURER_NAME,
            model=entity_description.key,
        )

        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_supported_features = entity_description.supported_features
        self._attr_preset_modes = entity_description.available_presets
        self._attr_fan_modes = entity_description.available_fan_modes
        self._attr_hvac_modes = [
            HVACMode(mode) for mode in entity_description.available_hvac_modes
        ]

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.device_id in self.coordinator.connector.all_devices
        )

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self.get_parameter_value(CompitParameter.CURRENT_TEMPERATURE)
        if value is None:
            return None
        return float(value)

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        value = self.get_parameter_value(CompitParameter.SET_TARGET_TEMPERATURE)
        if value is None:
            return None
        return float(value)

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        preset_mode = self.get_parameter_value(CompitParameter.PRESET_MODE)

        if preset_mode is not None:
            compit_preset_mode = CompitPresetMode(preset_mode)
            return COMPIT_PRESET_MAP.get(compit_preset_mode)
        return None

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self.get_parameter_value(CompitParameter.FAN_MODE)
        if fan_mode is not None:
            compit_fan_mode = CompitFanMode(fan_mode)
            return COMPIT_FANSPEED_MAP.get(compit_fan_mode)
        return None

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        hvac_mode = self.get_parameter_value(CompitParameter.HVAC_MODE)
        if hvac_mode is not None:
            compit_hvac_mode = CompitHVACMode(hvac_mode)
            return COMPIT_MODE_MAP.get(compit_hvac_mode)
        return None

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            raise ServiceValidationError("Temperature argument missing")
        await self.set_parameter_value(CompitParameter.SET_TARGET_TEMPERATURE, temp)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""

        if not (mode := HVAC_MODE_TO_COMPIT_MODE.get(hvac_mode)):
            raise ServiceValidationError(f"Invalid hvac mode {hvac_mode}")

        await self.set_parameter_value(CompitParameter.HVAC_MODE, mode.value)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""

        compit_preset = PRESET_MODE_TO_COMPIT_PRESET_MODE.get(preset_mode)
        if compit_preset is None:
            raise ServiceValidationError(f"Invalid preset mode: {preset_mode}")

        await self.set_parameter_value(CompitParameter.PRESET_MODE, compit_preset.value)

    @override
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

    def get_parameter_value(self, parameter: CompitParameter) -> str | float | None:
        """Get the parameter value from the device state."""
        return self.coordinator.connector.get_current_value(self.device_id, parameter)
