"""Climate platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

import asyncio
from typing import Any

from pysaunum import MAX_TEMPERATURE, MIN_TEMPERATURE, SaunumException

from homeassistant.components.climate import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry
from .const import DELAYED_REFRESH_SECONDS, DOMAIN
from .entity import LeilSaunaEntity

PARALLEL_UPDATES = 1

# Map Saunum fan speed (0-3) to Home Assistant fan modes
FAN_SPEED_TO_MODE = {
    0: FAN_OFF,
    1: FAN_LOW,
    2: FAN_MEDIUM,
    3: FAN_HIGH,
}
FAN_MODE_TO_SPEED = {v: k for k, v in FAN_SPEED_TO_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna climate entity."""
    coordinator = entry.runtime_data
    async_add_entities([LeilSaunaClimate(coordinator)])


class LeilSaunaClimate(LeilSaunaEntity, ClimateEntity):
    """Representation of a Saunum Leil Sauna climate entity."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE
    _attr_fan_modes = [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature in Celsius."""
        return self.coordinator.data.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature in Celsius."""
        return self.coordinator.data.target_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_speed = self.coordinator.data.fan_speed
        if fan_speed is not None and fan_speed in FAN_SPEED_TO_MODE:
            return FAN_SPEED_TO_MODE[fan_speed]
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        session_active = self.coordinator.data.session_active
        return HVACMode.HEAT if session_active else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        if not self.coordinator.data.session_active:
            return HVACAction.OFF

        heater_elements_active = self.coordinator.data.heater_elements_active
        return (
            HVACAction.HEATING
            if heater_elements_active and heater_elements_active > 0
            else HVACAction.IDLE
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.HEAT and self.coordinator.data.door_open:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="door_open",
            )

        try:
            if hvac_mode == HVACMode.HEAT:
                await self.coordinator.client.async_start_session()
            else:
                await self.coordinator.client.async_stop_session()
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_hvac_mode_failed",
                translation_placeholders={"hvac_mode": hvac_mode},
            ) from err

        # The device takes 1-2 seconds to turn heater elements on/off and
        # update heater_elements_active. Wait and refresh again to ensure
        # the HVAC action state reflects the actual heater status.
        await asyncio.sleep(DELAYED_REFRESH_SECONDS.total_seconds())
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        try:
            await self.coordinator.client.async_set_target_temperature(
                int(kwargs[ATTR_TEMPERATURE])
            )
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
                translation_placeholders={"temperature": str(kwargs[ATTR_TEMPERATURE])},
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if not self.coordinator.data.session_active:
            raise ServiceValidationError(
                "Cannot change fan mode when sauna session is not active",
                translation_domain=DOMAIN,
                translation_key="session_not_active",
            )

        await self.coordinator.client.async_set_fan_speed(FAN_MODE_TO_SPEED[fan_mode])
        await self.coordinator.async_request_refresh()
