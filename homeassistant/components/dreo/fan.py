"""Support for Dreo fans."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import percentage_to_ordered_list_item

from . import DreoConfigEntry
from .const import (
    ERROR_SET_OSCILLATE_FAILED,
    ERROR_SET_PRESET_MODE_FAILED,
    ERROR_SET_SPEED_FAILED,
    ERROR_TURN_OFF_FAILED,
    ERROR_TURN_ON_FAILED,
    FIELD_MODE,
    FIELD_OSCILLATE,
    FIELD_POWER_ON,
    FIELD_SPEED,
)
from .coordinator import (
    DreoDataUpdateCoordinator,
    get_fan_model_config,
    get_speed_values,
)
from .entity import DreoEntity

UNIQUE_ID_SUFFIX = "fan"
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fans from a config entry."""
    async_add_entities(
        DreoFan(coordinator)
        for coordinator in config_entry.runtime_data.coordinators.values()
    )


class DreoFan(DreoEntity, FanEntity):
    """Dreo fan."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_is_on = False
    _attr_percentage = 0
    _attr_preset_mode = None
    _attr_oscillating = None
    _attr_speed_count = 100

    def __init__(self, coordinator: DreoDataUpdateCoordinator) -> None:
        """Initialize the Dreo fan."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{UNIQUE_ID_SUFFIX}"

        model_config = coordinator.model_config
        fan_model_config = get_fan_model_config(model_config)
        self._speed_values = get_speed_values(model_config) or []
        if self._speed_values:
            self._attr_speed_count = len(self._speed_values)
        self._attr_preset_modes = fan_model_config.get("preset_modes")

    async def async_added_to_hass(self) -> None:
        """Register the fan and sync its initial state."""
        await super().async_added_to_hass()
        self._update_attributes()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self) -> None:
        """Update attributes from coordinator data."""
        if not self.coordinator.data:
            return

        fan_state_data = self.coordinator.data
        self._attr_is_on = fan_state_data.is_on

        if not fan_state_data.is_on:
            self._attr_percentage = 0
            self._attr_preset_mode = None
            self._attr_oscillating = None
        else:
            self._attr_preset_mode = fan_state_data.mode
            self._attr_oscillating = fan_state_data.oscillate
            self._attr_percentage = fan_state_data.speed_percentage or 0

    @property
    def is_on(self) -> bool | None:
        """Return whether the fan is on."""
        return self._attr_is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if percentage is not None and percentage <= 0:
            await self.async_turn_off()
            return

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[FIELD_POWER_ON] = True

        if percentage is not None and self._speed_values:
            speed = percentage_to_ordered_list_item(self._speed_values, percentage)
            if speed != percentage_to_ordered_list_item(
                self._speed_values, self.percentage or 0
            ):
                command_params[FIELD_SPEED] = speed

        if preset_mode is not None and preset_mode != self.preset_mode:
            command_params[FIELD_MODE] = preset_mode

        if not command_params:
            return

        await self.async_send_command(ERROR_TURN_ON_FAILED, **command_params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.async_send_command(ERROR_TURN_OFF_FAILED, **{FIELD_POWER_ON: False})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[FIELD_POWER_ON] = True

        if preset_mode != self.preset_mode:
            command_params[FIELD_MODE] = preset_mode

        if not command_params:
            return

        await self.async_send_command(ERROR_SET_PRESET_MODE_FAILED, **command_params)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""
        if percentage <= 0:
            await self.async_turn_off()
            return

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[FIELD_POWER_ON] = True

        if self._speed_values:
            speed = percentage_to_ordered_list_item(self._speed_values, percentage)
            if speed != percentage_to_ordered_list_item(
                self._speed_values, self.percentage or 0
            ):
                command_params[FIELD_SPEED] = speed

        if not command_params:
            return

        await self.async_send_command(ERROR_SET_SPEED_FAILED, **command_params)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the oscillation of fan."""
        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[FIELD_POWER_ON] = True

        if oscillating != self.oscillating:
            command_params[FIELD_OSCILLATE] = oscillating

        if not command_params:
            return

        await self.async_send_command(ERROR_SET_OSCILLATE_FAILED, **command_params)
