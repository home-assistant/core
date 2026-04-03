"""Support for Dreo fans."""

from __future__ import annotations

import logging
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
    FAN_DEVICE_TYPE,
)
from .coordinator import (
    DreoDataUpdateCoordinator,
    get_fan_model_config,
    get_speed_values,
)
from .entity import DreoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fans from a config entry."""

    @callback
    def async_add_fan_devices() -> None:
        """Add fan devices."""
        new_fans = []

        for device in config_entry.runtime_data.devices:
            device_type = device.get("deviceType")
            if device_type is None:
                continue

            if device_type != FAN_DEVICE_TYPE:
                continue

            device_id = device.get("deviceSn")
            if not device_id:
                continue

            coordinator = config_entry.runtime_data.coordinators.get(device_id)
            if not coordinator:
                _LOGGER.error("Coordinator not found for device %s", device_id)
                continue

            fan = DreoFan(device, coordinator)
            new_fans.append(fan)

        if new_fans:
            async_add_entities(new_fans)

    async_add_fan_devices()


class DreoFan(DreoEntity, FanEntity):
    """Dreo fan."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_percentage = 0
    _attr_preset_mode = None
    _attr_oscillating = None
    _attr_speed_count = 100

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo fan."""
        super().__init__(device, coordinator, FAN_DEVICE_TYPE)

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
        if not self.coordinator.data:
            return None

        return self.coordinator.data.is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        await self.async_execute_fan_common_command(
            ERROR_TURN_ON_FAILED, percentage=percentage, preset_mode=preset_mode
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.async_send_command_and_update(
            ERROR_TURN_OFF_FAILED, power_switch=False
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        await self.async_execute_fan_common_command(
            ERROR_SET_PRESET_MODE_FAILED, preset_mode=preset_mode
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""

        if percentage <= 0:
            await self.async_turn_off()
            return

        await self.async_execute_fan_common_command(
            ERROR_SET_SPEED_FAILED, percentage=percentage
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the oscillation of fan."""
        await self.async_execute_fan_common_command(
            ERROR_SET_OSCILLATE_FAILED, oscillate=oscillating
        )

    async def async_execute_fan_common_command(
        self,
        error_translation_key: str,
        percentage: int | None = None,
        preset_mode: str | None = None,
        oscillate: bool | None = None,
    ) -> None:
        """Execute fan command with common parameter handling."""

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params["power_switch"] = True

        if percentage is not None and percentage > 0 and self._speed_values:
            speed = percentage_to_ordered_list_item(self._speed_values, percentage)
            current_percentage = self.percentage
            current_speed = (
                percentage_to_ordered_list_item(self._speed_values, current_percentage)
                if current_percentage
                else None
            )
            if speed > 0 and speed != current_speed:
                command_params["speed"] = speed

        if preset_mode is not None:
            command_params["mode"] = preset_mode
        if oscillate is not None:
            command_params["oscillate"] = oscillate

        if not command_params:
            return

        await self.async_send_command_and_update(
            error_translation_key, **command_params
        )
