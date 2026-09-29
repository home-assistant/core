"""Climate for Electrolux Integration."""

from abc import ABC, abstractmethod
import logging
from typing import Any, override

from electrolux_group_developer_sdk.client.appliances.ac_appliance import ACAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.dam_ac_appliance import (
    DAMACAppliance,
)
from electrolux_group_developer_sdk.constants import (
    APPLIANCE_STATE_IDLE,
    APPLIANCE_STATE_OFF,
)

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    FAN_AUTO,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ELECTROLUX_TO_HA_TEMPERATURE_UNIT
from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import round_to_multiple_of_step

_LOGGER = logging.getLogger(__name__)

ELECTROLUX_TO_HA_MODES = {
    "HEAT": HVACMode.HEAT,
    "COOL": HVACMode.COOL,
    "AUTO": HVACMode.AUTO,
    "DRY": HVACMode.DRY,
    "FANONLY": HVACMode.FAN_ONLY,
    "OFF": HVACMode.OFF,
    # ECO is missing
}
HA_TO_ELECTROLUX_MODES = {v: k for k, v in ELECTROLUX_TO_HA_MODES.items()}

ELECTROLUX_DAM_TO_HA_MODES = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "auto": HVACMode.AUTO,
    "dry": HVACMode.DRY,
    "fanOnly": HVACMode.FAN_ONLY,
    "off": HVACMode.OFF,
    # ECO is missing
}
HA_TO_ELECTROLUX_DAM_MODES = {v: k for k, v in ELECTROLUX_DAM_TO_HA_MODES.items()}

ELECTROLUX_TO_HA_FAN_SPEEDS = {
    "LOW": FAN_LOW,
    "MIDDLE": FAN_MEDIUM,
    "HIGH": FAN_HIGH,
    "TURBO": FAN_FOCUS,
    "AUTO": FAN_AUTO,
}
HA_TO_ELECTROLUX_FAN_SPEEDS = {v: k for k, v in ELECTROLUX_TO_HA_FAN_SPEEDS.items()}

ELECTROLUX_DAM_TO_HA_FAN_SPEEDS = {
    "low": FAN_LOW,
    "medium": FAN_MEDIUM,
    "high": FAN_HIGH,
    "turbo": FAN_FOCUS,
    "auto": FAN_AUTO,
}
HA_TO_ELECTROLUX_DAM_FAN_SPEEDS = {
    v: k for k, v in ELECTROLUX_DAM_TO_HA_FAN_SPEEDS.items()
}


class ElectroluxStringConverter[T](ABC):
    """Converter for string to value and vice versa."""

    @abstractmethod
    def map_to_string(self, value: T | None) -> str | None:
        """Map a value to a string representation."""

    @abstractmethod
    def map_from_string(self, value: str | None) -> T | None:
        """Map a string representation to a value."""


class ModeConverter(ElectroluxStringConverter[HVACMode]):
    """Converter for HVACMode to string and vice versa."""


class AcModeConverter(ModeConverter):
    """ModeConverter implementation for air conditioners."""

    @override
    def map_to_string(self, value: HVACMode | None) -> str | None:
        if value is None:
            return None
        return HA_TO_ELECTROLUX_MODES.get(value)

    @override
    def map_from_string(self, value: str | None) -> HVACMode | None:
        if value is None:
            return None
        return ELECTROLUX_TO_HA_MODES.get(value.upper())


class DamAcModeConverter(ModeConverter):
    """ModeConverter implementation for DAM air conditioners."""

    @override
    def map_to_string(self, value: HVACMode | None) -> str | None:
        if value is None:
            return None
        return HA_TO_ELECTROLUX_DAM_MODES.get(value)

    @override
    def map_from_string(self, value: str | None) -> HVACMode | None:
        if value is None:
            return None
        return ELECTROLUX_DAM_TO_HA_MODES.get(value)


class FanSpeedConverter(ElectroluxStringConverter[str]):
    """Converter for fan speed to string and vice versa."""


class AcFanSpeedConverter(FanSpeedConverter):
    """FanSpeedConverter implementation for air conditioners."""

    @override
    def map_to_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        return HA_TO_ELECTROLUX_FAN_SPEEDS.get(value)

    @override
    def map_from_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        return ELECTROLUX_TO_HA_FAN_SPEEDS.get(value.upper())


class DamAcFanSpeedConverter(FanSpeedConverter):
    """FanSpeedConverter implementation for DAM air conditioners."""

    @override
    def map_to_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        return HA_TO_ELECTROLUX_DAM_FAN_SPEEDS.get(value)

    @override
    def map_from_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        return ELECTROLUX_DAM_TO_HA_FAN_SPEEDS.get(value)


AC_MODE_CONVERTER = AcModeConverter()
DAM_AC_MODE_CONVERTER = DamAcModeConverter()
AC_FAN_SPEED_CONVERTER = AcFanSpeedConverter()
DAM_AC_FAN_SPEED_CONVERTER = DamAcFanSpeedConverter()


def _is_off(mode: str | None) -> bool:
    return mode is not None and mode.upper() in (
        APPLIANCE_STATE_OFF,
        APPLIANCE_STATE_IDLE,
    )


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, ACAppliance):
        entities.append(
            ElectroluxClimateEntity(
                appliance_data=appliance_data,
                coordinator=coordinator,
            )
        )

    if isinstance(appliance_data, DAMACAppliance):
        entities.append(
            ElectroluxDamClimateEntity(
                appliance_data=appliance_data, coordinator=coordinator
            )
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set Climate entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBaseClimate[T: ACAppliance | DAMACAppliance](
    ElectroluxBaseEntity[T], ClimateEntity, ABC
):
    """Base class used for Electrolux AC units."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.FAN_MODE
    )
    _attr_target_temperature_step: float

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        mode_converter: ModeConverter,
        fan_speed_converter: FanSpeedConverter,
    ) -> None:
        """Initialize the climate device."""
        entity_key = "climate"
        translation_key = "climate"
        super().__init__(appliance_data, coordinator, entity_key)
        self._mode_converter = mode_converter
        self._fan_speed_converter = fan_speed_converter

        self._attr_key = entity_key
        self._attr_translation_key = translation_key
        self._attr_hvac_modes = self._get_hvac_supported_mode()
        self._attr_fan_modes = self._get_fan_supported_mode()

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_target_temperature_step = (
            self._appliance_data.get_supported_step_temp()
        )
        self._attr_min_temp = self._appliance_data.get_supported_min_temp()
        self._attr_max_temp = self._appliance_data.get_supported_max_temp()
        self._attr_hvac_mode = None
        self._attr_fan_mode = None

    def _state_snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the current state."""
        return {
            "hvac_mode": self._attr_hvac_mode,
            "fan_mode": self._attr_fan_mode,
            "current_temperature": self._attr_current_temperature,
            "target_temperature": self._attr_target_temperature,
            "temperature_unit": self._attr_temperature_unit,
            "min_temp": self._attr_min_temp,
            "max_temp": self._attr_max_temp,
            "target_temperature_step": self._attr_target_temperature_step,
        }

    @override
    def _update_attr_state(self) -> bool:
        old_state_snapshot = self._state_snapshot()

        # Set temperature
        self._attr_temperature_unit = self._get_temperature_unit()
        self._attr_current_temperature = self._get_ambient_temperature()
        self._attr_target_temperature = self._get_target_temperature()
        self._attr_min_temp = self._appliance_data.get_supported_min_temp()
        self._attr_max_temp = self._appliance_data.get_supported_max_temp()
        self._attr_target_temperature_step = (
            self._appliance_data.get_supported_step_temp()
        )
        # Set current mode
        self._attr_hvac_mode = self._get_hvac_mode()
        # Set fan speed
        self._attr_fan_mode = self._get_fan_speed()

        new_state_snapshot = self._state_snapshot()

        return old_state_snapshot != new_state_snapshot

    def _get_hvac_supported_mode(self) -> list[HVACMode]:
        available_modes = self._appliance_data.get_supported_modes()
        hvac_modes: list[HVACMode] = [
            ha_mode
            for mode in available_modes
            if (ha_mode := self._mode_converter.map_from_string(mode)) is not None
        ]
        if HVACMode.OFF not in hvac_modes:
            hvac_modes.append(HVACMode.OFF)
        return hvac_modes

    def _get_fan_supported_mode(self) -> list[str]:
        available_fan_speeds = self._appliance_data.get_supported_fan_speeds()
        fan_modes: list[str] = [
            ha_fan_speed
            for fan_speed in available_fan_speeds
            if (ha_fan_speed := self._fan_speed_converter.map_from_string(fan_speed))
            is not None
        ]
        return fan_modes

    def _get_hvac_mode(self) -> HVACMode | None:
        """Return hvac target mode."""
        current_appliance_state = self._appliance_data.get_current_appliance_state()
        if _is_off(current_appliance_state):
            return HVACMode.OFF

        current_mode = self._appliance_data.get_current_mode()
        return self._mode_converter.map_from_string(current_mode)

    def _get_fan_speed(self) -> str | None:
        """Return fan speed."""
        current_fan_speed = self._appliance_data.get_current_fan_speed()
        return self._fan_speed_converter.map_from_string(current_fan_speed)

    def _get_temperature_unit(self) -> UnitOfTemperature:
        """Return current temperature unit. Return Celsius as default."""
        temp_unit = self._appliance_data.get_current_temperature_unit()

        if temp_unit is not None:
            temp_unit = temp_unit.upper()

        return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(
            temp_unit, UnitOfTemperature.CELSIUS
        )

    @abstractmethod
    def _get_target_temperature(self) -> float | None:
        """Return current target temperature."""

    @abstractmethod
    def _get_ambient_temperature(self) -> float | None:
        """Return current ambient temperature."""

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Handle changing fan mode."""
        fan_speed = self._fan_speed_converter.map_to_string(fan_mode)
        if fan_speed is None:
            return
        command = self._appliance_data.get_fan_speed_command(fan_speed)
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Handle changing HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._turn_off_appliance()
        else:
            await self._set_appliance_mode(hvac_mode)

    @override
    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self._turn_on_appliance()

    @override
    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self._turn_off_appliance()

    async def _turn_on_appliance(self) -> None:
        command = self._appliance_data.get_turn_on_command()
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    async def _turn_off_appliance(self) -> None:
        command = self._appliance_data.get_turn_off_command()
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    async def _set_appliance_mode(self, mode: HVACMode) -> None:
        current_mode = self._appliance_data.get_current_mode()
        current_appliance_state = self._appliance_data.get_current_appliance_state()
        command: dict[str, Any] = {}

        if _is_off(current_appliance_state):
            command = _combine_commands(
                command, self._appliance_data.get_turn_on_command()
            )
        if (
            new_mode := self._mode_converter.map_to_string(mode)
        ) is not None and new_mode != current_mode:
            command = _combine_commands(
                command, self._appliance_data.get_mode_command(new_mode)
            )

        if command:
            await self.coordinator.client.send_command(self._appliance_id, command)
            await self.coordinator.async_refresh()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature: float | None = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        rounded_temperature = round_to_multiple_of_step(
            temperature, self._attr_target_temperature_step
        )
        command = self._get_temperature_command(rounded_temperature)

        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @abstractmethod
    def _get_temperature_command(self, temperature: float) -> dict[str, Any]:
        """Return the command payload to set the temperature."""


class ElectroluxClimateEntity(ElectroluxBaseClimate[ACAppliance], ClimateEntity):
    """Representation of an Electrolux AC unit."""

    def __init__(
        self,
        appliance_data: ACAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(
            appliance_data, coordinator, AC_MODE_CONVERTER, AC_FAN_SPEED_CONVERTER
        )

    @override
    def _get_target_temperature(self) -> float | None:
        """Return current target temperature."""
        if self._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return self._appliance_data.get_current_target_temperature_f()

        return self._appliance_data.get_current_target_temperature_c()

    @override
    def _get_ambient_temperature(self) -> float | None:
        """Return current ambient temperature."""
        if self._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return self._appliance_data.get_current_ambient_temperature_f()

        return self._appliance_data.get_current_ambient_temperature_c()

    @override
    def _get_temperature_command(self, temperature: float) -> dict[str, Any]:
        """Return the command payload to set the temperature."""
        if self._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return self._appliance_data.get_temperature_f_command(temperature)

        return self._appliance_data.get_temperature_c_command(temperature)


class ElectroluxDamClimateEntity(ElectroluxBaseClimate[DAMACAppliance], ClimateEntity):
    """Representation of an Electrolux DAM AC unit."""

    def __init__(
        self,
        appliance_data: DAMACAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(
            appliance_data,
            coordinator,
            DAM_AC_MODE_CONVERTER,
            DAM_AC_FAN_SPEED_CONVERTER,
        )

    @override
    def _get_target_temperature(self) -> float | None:
        """Return current target temperature."""
        return self._appliance_data.get_current_target_temperature()

    @override
    def _get_ambient_temperature(self) -> float | None:
        """Return current ambient temperature."""
        return self._appliance_data.get_current_ambient_temperature()

    @override
    def _get_temperature_command(self, temperature: float) -> dict[str, Any]:
        """Return the command payload to set the temperature."""
        return self._appliance_data.get_temperature_command(temperature)


def _combine_commands(
    command1: dict[str, Any], command2: dict[str, Any]
) -> dict[str, Any]:
    combined_command = command1.copy()
    for key, value in command2.items():
        if key in combined_command:
            if isinstance(combined_command[key], dict) and isinstance(value, dict):
                combined_command[key] = _combine_commands(combined_command[key], value)
            else:
                raise ValueError(f"Conflict in command keys: {key}")
        else:
            combined_command[key] = value
    return combined_command
