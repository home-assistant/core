"""Support for climate entities."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.integration import ExtendedProperty

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_NONE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity

DEVICE_TYPE_CLIMATE_MAP: dict[DeviceType, tuple[ClimateEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        ClimateEntityDescription(
            key=ExtendedProperty.CLIMATE_AIR_CONDITIONER,
            name=None,
            translation_key=ExtendedProperty.CLIMATE_AIR_CONDITIONER,
        ),
    ),
    DeviceType.SYSTEM_BOILER: (
        ClimateEntityDescription(
            key=ExtendedProperty.CLIMATE_SYSTEM_BOILER,
            name=None,
            translation_key=ExtendedProperty.CLIMATE_SYSTEM_BOILER,
        ),
    ),
}

STR_TO_HVAC: dict[str, HVACMode] = {
    "air_dry": HVACMode.DRY,
    "auto": HVACMode.AUTO,
    "cool": HVACMode.COOL,
    "fan": HVACMode.FAN_ONLY,
    "heat": HVACMode.HEAT,
}

HVAC_TO_STR = {v: k for k, v in STR_TO_HVAC.items()}

THINQ_PRESET_MODE: list[str] = ["air_clean", "aroma", "energy_saving"]

STR_TO_SWING = {
    "true": SWING_ON,
    "false": SWING_OFF,
}

SWING_TO_STR = {v: k for k, v in STR_TO_SWING.items()}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for climate platform."""
    entities: list[ThinQClimateEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_CLIMATE_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQClimateEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(description.key)
                )

    if entities:
        async_add_entities(entities)


class ThinQClimateEntity(ThinQEntity, ClimateEntity):
    """Represent a thinq climate platform."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: ClimateEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize a climate entity."""
        super().__init__(coordinator, entity_description, property_id)

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        self._attr_hvac_modes = [HVACMode.OFF]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_preset_modes = [PRESET_NONE]
        self._attr_preset_mode = PRESET_NONE
        self._attr_temperature_unit = (
            self._get_unit_of_measurement(self.data.unit) or UnitOfTemperature.CELSIUS
        )

        # Set up HVAC modes.
        for mode in self.data.hvac_modes:
            if mode in STR_TO_HVAC:
                self._attr_hvac_modes.append(STR_TO_HVAC[mode])
            elif mode in THINQ_PRESET_MODE:
                self._attr_preset_modes.append(mode)
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        # Set up fan modes.
        self._attr_fan_modes = self.data.fan_modes
        if self.fan_modes:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        # Supports target temperature range.
        if self.data.support_temperature_range:
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
        # Supports swing mode.
        if self.data.swing_modes:
            self._attr_swing_modes = [SWING_ON, SWING_OFF]
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        if self.data.swing_horizontal_modes:
            self._attr_swing_horizontal_modes = [SWING_ON, SWING_OFF]
            self._attr_supported_features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Update fan, hvac and preset mode.
        if self.supported_features & ClimateEntityFeature.FAN_MODE:
            self._attr_fan_mode = self.data.fan_mode
        if self.supported_features & ClimateEntityFeature.SWING_MODE:
            self._attr_swing_mode = STR_TO_SWING.get(self.data.swing_mode)
        if self.supported_features & ClimateEntityFeature.SWING_HORIZONTAL_MODE:
            self._attr_swing_horizontal_mode = STR_TO_SWING.get(
                self.data.swing_horizontal_mode
            )

        if self.data.is_on:
            hvac_mode = self.data.hvac_mode
            if hvac_mode in STR_TO_HVAC:
                self._attr_hvac_mode = STR_TO_HVAC.get(hvac_mode)
                self._attr_preset_mode = PRESET_NONE
            elif hvac_mode in THINQ_PRESET_MODE:
                self._attr_hvac_mode = (
                    HVACMode.COOL if hvac_mode == "energy_saving" else HVACMode.FAN_ONLY
                )
                self._attr_preset_mode = hvac_mode
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_preset_mode = PRESET_NONE

        self._attr_current_humidity = self.data.humidity
        self._attr_current_temperature = self.data.current_temp

        # Update min, max and step.
        if self.data.max is not None:
            self._attr_max_temp = self.data.max
        if self.data.min is not None:
            self._attr_min_temp = self.data.min

        self._attr_target_temperature_step = self.data.step

        # Update target temperatures.
        self._attr_target_temperature = self.data.target_temp
        self._attr_target_temperature_high = self.data.target_temp_high
        self._attr_target_temperature_low = self.data.target_temp_low

        # Update unit.
        self._attr_temperature_unit = (
            self._get_unit_of_measurement(self.data.unit) or UnitOfTemperature.CELSIUS
        )

        _LOGGER.debug(
            "[%s:%s] update status: c:%s, t:%s, l:%s, h:%s, hvac:%s, unit:%s, step:%s",
            self.coordinator.device_name,
            self.property_id,
            self.current_temperature,
            self.target_temperature,
            self.target_temperature_low,
            self.target_temperature_high,
            self.hvac_mode,
            self.temperature_unit,
            self.target_temperature_step,
        )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        _LOGGER.debug(
            "[%s:%s] async_turn_on", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(self.coordinator.api.async_turn_on(self.property_id))

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        _LOGGER.debug(
            "[%s:%s] async_turn_off", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(self.coordinator.api.async_turn_off(self.property_id))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        if hvac_mode == HVACMode.HEAT_COOL:
            hvac_mode = HVACMode.AUTO

        # If device is off, turn on first.
        if not self.data.is_on:
            await self.async_turn_on()

        _LOGGER.debug(
            "[%s:%s] async_set_hvac_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            hvac_mode,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_hvac_mode(
                self.property_id, HVAC_TO_STR.get(hvac_mode)
            )
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug(
            "[%s:%s] async_set_preset_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            preset_mode,
        )
        if preset_mode == PRESET_NONE:
            preset_mode = "cool" if self.preset_mode == "energy_saving" else "fan"
        await self.async_call_api(
            self.coordinator.api.async_set_hvac_mode(self.property_id, preset_mode)
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        _LOGGER.debug(
            "[%s:%s] async_set_fan_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            fan_mode,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_fan_mode(self.property_id, fan_mode)
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        _LOGGER.debug(
            "[%s:%s] async_set_swing_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            swing_mode,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_swing_mode(
                self.property_id, SWING_TO_STR.get(swing_mode)
            )
        )

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new swing horizontal mode."""
        _LOGGER.debug(
            "[%s:%s] async_set_swing_horizontal_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            swing_horizontal_mode,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_swing_horizontal_mode(
                self.property_id, SWING_TO_STR.get(swing_horizontal_mode)
            )
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if hvac_mode := kwargs.get(ATTR_HVAC_MODE):
            if hvac_mode == HVACMode.OFF:
                await self.async_turn_off()
                return

            if hvac_mode == HVACMode.HEAT_COOL:
                hvac_mode = HVACMode.AUTO

        # If device is off, turn on first.
        if not self.data.is_on:
            await self.async_turn_on()

        if hvac_mode and hvac_mode != self.hvac_mode:
            await self.async_set_hvac_mode(HVACMode(hvac_mode))

        _LOGGER.debug(
            "[%s:%s] async_set_temperature: %s",
            self.coordinator.device_name,
            self.property_id,
            kwargs,
        )
        if temperature := kwargs.get(ATTR_TEMPERATURE):
            if self.data.step >= 1:
                temperature = int(temperature)
            if temperature != self.target_temperature:
                await self.async_call_api(
                    self.coordinator.api.async_set_target_temperature(
                        self.property_id,
                        temperature,
                    )
                )

        if (temperature_low := kwargs.get(ATTR_TARGET_TEMP_LOW)) and (
            temperature_high := kwargs.get(ATTR_TARGET_TEMP_HIGH)
        ):
            if self.data.step >= 1:
                temperature_low = int(temperature_low)
                temperature_high = int(temperature_high)
            await self.async_call_api(
                self.coordinator.api.async_set_target_temperature_low_high(
                    self.property_id,
                    temperature_low,
                    temperature_high,
                )
            )
