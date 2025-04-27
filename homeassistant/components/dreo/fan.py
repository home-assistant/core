"""Support for Dreo fans."""

from __future__ import annotations

import math
from typing import Any

from hscloud.const import DEVICE_TYPE, FAN_DEVICE

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import percentage_to_ranged_value

from . import DreoConfigEntry
from .const import (
    ERROR_SET_OSCILLATE_FAILED,
    ERROR_SET_PRESET_MODE_FAILED,
    ERROR_SET_SPEED_FAILED,
    ERROR_TURN_OFF_FAILED,
    ERROR_TURN_ON_FAILED,
)
from .coordinator import DreoDataUpdateCoordinator
from .entity import DreoEntity

FAN_SUFFIX = "fan"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fan from a config entry."""
    # Simple cleanup of stale entities
    device_ids = {
        str(d.get("deviceSn", ""))
        for d in config_entry.runtime_data.devices
        if d.get("deviceSn")
    }
    entity_registry = er.async_get(hass)

    [
        entity_registry.async_remove(entry.entity_id)
        for entry in entity_registry.entities.values()
        if entry.config_entry_id == config_entry.entry_id
        and entry.domain == "fan"
        and (
            entry.unique_id.split("_")[0] if "_" in entry.unique_id else entry.unique_id
        )
        not in device_ids
    ]

    # Add current devices
    fan_devices = []
    for device in config_entry.runtime_data.devices:
        device_model = device.get("model")
        if DEVICE_TYPE.get(device_model) is None:
            continue

        device_id = str(device.get("deviceSn", ""))
        if not device_id:
            continue

        coordinator = config_entry.runtime_data.coordinators.get(device_id)
        if not coordinator:
            continue

        fan_devices.append(DreoFan(device, coordinator))

    async_add_entities(fan_devices)


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

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo fan."""
        super().__init__(device, coordinator, FAN_SUFFIX, None)

        model_config = FAN_DEVICE.get("config", {}).get(self._model, {})
        speed_range = model_config.get("speed_range")

        self._attr_preset_modes = model_config.get("preset_modes")
        self._low_high_range = speed_range

        # Update attributes from coordinator data
        self._update_attributes()

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()

    def _update_attributes(self):
        """Update attributes from coordinator data."""
        if not self.coordinator.data:
            return

        fan_state_data = self.coordinator.data
        if fan_state_data["available"] is False:
            self._attr_available = False
            return

        self._attr_available = fan_state_data.get("connected")

        if not fan_state_data["is_on"]:
            self._attr_percentage = 0
            self._attr_preset_mode = None
            self._attr_oscillating = None
        else:
            self._attr_preset_mode = fan_state_data.get("mode")
            self._attr_oscillating = fan_state_data.get("oscillate")
            self._attr_percentage = fan_state_data.get("speed_percentage")

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on.

        Args:
            percentage: Optional speed percentage (0-100)
            preset_mode: Optional preset mode to set
            **kwargs: Additional parameters passed to parent classes

        """

        speed = None
        if percentage is not None and percentage > 0 and self._low_high_range:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )

        await self.async_execute_fan_common_command(
            ERROR_TURN_ON_FAILED, speed=speed, preset_mode=preset_mode
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
        """Set the speed of fan.

        Converts the percentage (0-100) to the device's native speed range.
        A percentage of 0 will turn the fan off.

        Args:
            percentage: Speed percentage (0-100)

        """
        if percentage <= 0:
            await self.async_turn_off()
            return

        speed = math.ceil(percentage_to_ranged_value(self._low_high_range, percentage))
        await self.async_execute_fan_common_command(ERROR_SET_SPEED_FAILED, speed=speed)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the oscillation of fan."""
        await self.async_execute_fan_common_command(
            ERROR_SET_OSCILLATE_FAILED, oscillate=oscillating
        )

    async def async_execute_fan_common_command(
        self,
        translation_key: str,
        speed: int | None = None,
        preset_mode: str | None = None,
        oscillate: bool | None = None,
    ) -> None:
        """Execute fan command with common parameter handling.

        This helper method consolidates common fan command logic:
        - Automatically turns on the fan if it's off
        - Handles speed, preset mode and oscillation parameters
        - Sends the appropriate command to the device

        Args:
            translation_key: Error translation key for error messages
            speed: Fan speed (optional)
            preset_mode: Fan mode (optional)
            oscillate: Oscillation state (optional)

        """

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params["power_switch"] = True
        if speed is not None and speed > 0:
            command_params["speed"] = speed
        if preset_mode is not None:
            command_params["mode"] = preset_mode
        if oscillate is not None:
            command_params["oscillate"] = oscillate

        await self.async_send_command_and_update(translation_key, **command_params)
