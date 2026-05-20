"""Support for Dreo fans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

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
from .coordinator import DreoDataUpdateCoordinator
from .entity import DreoEntity

PARALLEL_UPDATES = 0


@dataclass(slots=True)
class DreoFanStateData:
    """Processed Dreo fan state for the fan entity."""

    is_on: bool
    mode: str | None = None
    oscillate: bool | None = None
    speed_percentage: int | None = None


def _get_fan_model_config(model_config: dict[str, Any]) -> dict[str, Any]:
    """Return the fan-specific model config section."""
    if isinstance(model_config.get("fan_entity_config"), dict):
        return model_config["fan_entity_config"]

    return model_config


def _get_speed_values(model_config: dict[str, Any]) -> list[int] | None:
    """Return normalized supported fan speed values."""
    raw_speed_values = _get_fan_model_config(model_config).get("speed_range")

    if not isinstance(raw_speed_values, (list, tuple)) or len(raw_speed_values) < 2:
        return None

    try:
        speed_values = [int(value) for value in raw_speed_values]
    except TypeError, ValueError:
        return None

    if len(speed_values) == 2:
        low, high = speed_values
        if low < 1 or high < low:
            return None

        return list(range(low, high + 1))

    normalized_speed_values = sorted(set(speed_values))
    if normalized_speed_values[0] < 1:
        return None

    return normalized_speed_values


def process_fan_data(
    status: dict[str, Any], model_config: dict[str, Any]
) -> DreoFanStateData:
    """Process raw status data for the fan entity."""
    fan_state = DreoFanStateData(is_on=status.get(FIELD_POWER_ON) is True)

    if (mode := status.get(FIELD_MODE)) is not None:
        fan_state.mode = str(mode)

    if (oscillate := status.get(FIELD_OSCILLATE)) is not None:
        fan_state.oscillate = bool(oscillate)

    if (speed := status.get(FIELD_SPEED)) is not None:
        try:
            speed_value = int(float(speed))
        except TypeError, ValueError:
            speed_value = None

        if speed_value == 0:
            fan_state.speed_percentage = 0
        elif (
            speed_value is not None
            and (speed_values := _get_speed_values(model_config))
            and speed_value in speed_values
        ):
            fan_state.speed_percentage = ordered_list_item_to_percentage(
                speed_values, speed_value
            )

    return fan_state


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

    def __init__(self, coordinator: DreoDataUpdateCoordinator) -> None:
        """Initialize the Dreo fan."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device_id
        self._attr_supported_features = (
            FanEntityFeature.PRESET_MODE
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

        model_config = coordinator.model_config
        fan_model_config = _get_fan_model_config(model_config)
        self._speed_values = _get_speed_values(model_config) or []
        if self._speed_values:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            self._attr_speed_count = len(self._speed_values)
        self._attr_preset_modes = fan_model_config.get("preset_modes")
        if self.coordinator.data:
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

        fan_state_data = process_fan_data(
            self.coordinator.data, self.coordinator.model_config
        )
        self._attr_is_on = fan_state_data.is_on

        if not fan_state_data.is_on:
            self._attr_percentage = 0
            self._attr_preset_mode = None
            self._attr_oscillating = None
        else:
            self._attr_preset_mode = fan_state_data.mode
            self._attr_oscillating = fan_state_data.oscillate
            self._attr_percentage = fan_state_data.speed_percentage

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
        await self.async_send_command(ERROR_TURN_OFF_FAILED, poweron=False)

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
