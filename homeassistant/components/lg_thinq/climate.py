"""Support for climate entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.integration import ExtendedProperty

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.temperature import display_temp

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity


@dataclass(frozen=True, kw_only=True)
class ThinQClimateEntityDescription(ClimateEntityDescription):
    """Describes ThinQ climate entity."""

    min_temp: float | None = None
    max_temp: float | None = None
    step: float | None = None


DEVICE_TYPE_CLIMATE_MAP: dict[DeviceType, tuple[ThinQClimateEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        ThinQClimateEntityDescription(
            key=ExtendedProperty.CLIMATE_AIR_CONDITIONER,
            name=None,
            translation_key=ExtendedProperty.CLIMATE_AIR_CONDITIONER,
        ),
    ),
    DeviceType.SYSTEM_BOILER: (
        ThinQClimateEntityDescription(
            key=ExtendedProperty.CLIMATE_SYSTEM_BOILER,
            name=None,
            min_temp=16,
            max_temp=30,
            step=1,
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

HVAC_TO_STR: dict[HVACMode, str] = {
    HVACMode.AUTO: "auto",
    HVACMode.COOL: "cool",
    HVACMode.DRY: "air_dry",
    HVACMode.FAN_ONLY: "fan",
    HVACMode.HEAT: "heat",
}

THINQ_PRESET_MODE: list[str] = ["air_clean", "aroma", "energy_saving"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
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

    entity_description: ThinQClimateEntityDescription

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: ThinQClimateEntityDescription,
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
        self._attr_preset_modes = []
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._requested_hvac_mode: str | None = None

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

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Update fan, hvac and preset mode.
        if self.supported_features & ClimateEntityFeature.FAN_MODE:
            self._attr_fan_mode = self.data.fan_mode
        if self.data.is_on:
            hvac_mode = self._requested_hvac_mode or self.data.hvac_mode
            if hvac_mode in STR_TO_HVAC:
                self._attr_hvac_mode = STR_TO_HVAC.get(hvac_mode)
                self._attr_preset_mode = None
            elif hvac_mode in THINQ_PRESET_MODE:
                self._attr_preset_mode = hvac_mode
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_preset_mode = None

        self.reset_requested_hvac_mode()
        self._attr_current_humidity = self.data.humidity
        self._attr_current_temperature = self.data.current_temp

        # Update min, max and step.
        if (max_temp := self.entity_description.max_temp) is not None or (
            max_temp := self.data.max
        ) is not None:
            self._attr_max_temp = max_temp
        if (min_temp := self.entity_description.min_temp) is not None or (
            min_temp := self.data.min
        ) is not None:
            self._attr_min_temp = min_temp
        if (step := self.entity_description.step) is not None or (
            step := self.data.step
        ) is not None:
            self._attr_target_temperature_step = step

        # Update target temperatures.
        self._attr_target_temperature = self.data.target_temp
        self._attr_target_temperature_high = self.data.target_temp_high
        self._attr_target_temperature_low = self.data.target_temp_low

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

    def reset_requested_hvac_mode(self) -> None:
        """Cancel request to set hvac mode."""
        self._requested_hvac_mode = None

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

        # If device is off, turn on first.
        if not self.data.is_on:
            await self.async_turn_on()

        # When we request hvac mode while turning on the device, the previously set
        # hvac mode is displayed first and then switches to the requested hvac mode.
        # To prevent this, set the requested hvac mode here so that it will be set
        # immediately on the next update.
        self._requested_hvac_mode = HVAC_TO_STR.get(hvac_mode)

        _LOGGER.debug(
            "[%s:%s] async_set_hvac_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            hvac_mode,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_hvac_mode(
                self.property_id, self._requested_hvac_mode
            ),
            self.reset_requested_hvac_mode,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug(
            "[%s:%s] async_set_preset_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            preset_mode,
        )
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

    def _round_by_step(self, temperature: float) -> float:
        """Round the value by step."""
        if (
            target_temp := display_temp(
                self.coordinator.hass,
                temperature,
                self.coordinator.hass.config.units.temperature_unit,
                self.target_temperature_step or 1,
            )
        ) is not None:
            return target_temp

        return temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        _LOGGER.debug(
            "[%s:%s] async_set_temperature: %s",
            self.coordinator.device_name,
            self.property_id,
            kwargs,
        )

        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            if (
                target_temp := self._round_by_step(temperature)
            ) != self.target_temperature:
                await self.async_call_api(
                    self.coordinator.api.async_set_target_temperature(
                        self.property_id, target_temp
                    )
                )

        if (temperature_low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None:
            if (
                target_temp_low := self._round_by_step(temperature_low)
            ) != self.target_temperature_low:
                await self.async_call_api(
                    self.coordinator.api.async_set_target_temperature_low(
                        self.property_id, target_temp_low
                    )
                )

        if (temperature_high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            if (
                target_temp_high := self._round_by_step(temperature_high)
            ) != self.target_temperature_high:
                await self.async_call_api(
                    self.coordinator.api.async_set_target_temperature_high(
                        self.property_id, target_temp_high
                    )
                )
