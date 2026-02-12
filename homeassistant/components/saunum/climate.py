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
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .const import (
    DEFAULT_PRESET_NAME_TYPE_1,
    DEFAULT_PRESET_NAME_TYPE_2,
    DEFAULT_PRESET_NAME_TYPE_3,
    DELAYED_REFRESH_SECONDS,
    DOMAIN,
    OPT_PRESET_NAME_TYPE_1,
    OPT_PRESET_NAME_TYPE_2,
    OPT_PRESET_NAME_TYPE_3,
)
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
    _attr_translation_key = "saunum_climate"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 1.0
    _attr_min_temp = MIN_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE
    _attr_fan_modes = [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _preset_name_map: dict[int, str]

    def __init__(self, coordinator: LeilSaunaCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._update_preset_names()

    def _update_preset_names(self) -> None:
        """Update preset names from config entry options."""
        options = self.coordinator.config_entry.options
        self._preset_name_map = {
            0: options.get(OPT_PRESET_NAME_TYPE_1, DEFAULT_PRESET_NAME_TYPE_1),
            1: options.get(OPT_PRESET_NAME_TYPE_2, DEFAULT_PRESET_NAME_TYPE_2),
            2: options.get(OPT_PRESET_NAME_TYPE_3, DEFAULT_PRESET_NAME_TYPE_3),
        }
        self._attr_preset_modes = list(self._preset_name_map.values())

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.config_entry.add_update_listener(
                self._async_update_listener
            )
        )

    async def _async_update_listener(
        self, hass: HomeAssistant, entry: LeilSaunaConfigEntry
    ) -> None:
        """Handle options update."""
        self._update_preset_names()
        self.async_write_ha_state()

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

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        sauna_type = self.coordinator.data.sauna_type
        if sauna_type is not None and sauna_type in self._preset_name_map:
            return self._preset_name_map[sauna_type]
        return self._preset_name_map[0]

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
                translation_domain=DOMAIN,
                translation_key="session_not_active",
            )

        try:
            await self.coordinator.client.async_set_fan_speed(
                FAN_MODE_TO_SPEED[fan_mode]
            )
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_fan_mode_failed",
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode (sauna type)."""
        if self.coordinator.data.session_active:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="preset_session_active",
            )

        # Find the sauna type value from the preset name
        sauna_type_value = 0  # Default to type 1
        for type_value, type_name in self._preset_name_map.items():
            if type_name == preset_mode:
                sauna_type_value = type_value
                break

        try:
            await self.coordinator.client.async_set_sauna_type(sauna_type_value)
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_preset_failed",
                translation_placeholders={"preset_mode": preset_mode},
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_start_session(
        self,
        duration: int = 120,
        target_temperature: int = 80,
        fan_duration: int = 10,
    ) -> None:
        """Start a sauna session with custom parameters."""
        if self.coordinator.data.door_open:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="door_open",
            )

        try:
            # Set all parameters before starting the session
            await self.coordinator.client.async_set_sauna_duration(duration)
            await self.coordinator.client.async_set_target_temperature(
                target_temperature
            )
            await self.coordinator.client.async_set_fan_duration(fan_duration)
            await self.coordinator.client.async_start_session()
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="start_session_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        await self.coordinator.async_request_refresh()
