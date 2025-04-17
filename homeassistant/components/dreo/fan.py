"""Support for Dreo fans."""

from __future__ import annotations

import logging
import math
from typing import Any

from hscloud.const import DEVICE_TYPE, FAN_DEVICE

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

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
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fan from a config entry."""
    client = config_entry.runtime_data.client
    fan_devices = []

    for device in config_entry.runtime_data.devices:
        device_model = device.get("model")
        if DEVICE_TYPE.get(device_model) != FAN_DEVICE.get("type"):
            continue

        device_id = device.get("deviceSn")
        if not device_id:
            continue

        # Create coordinator for this device
        coordinator = DreoDataUpdateCoordinator(hass, client, device_id)

        # Fetch initial data
        await coordinator.async_config_entry_first_refresh()

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
        self._attr_speed_count = int_states_in_range(speed_range) if speed_range else 0

    @property
    def is_on(self) -> bool:
        """Return true if the entity is on."""
        return self.coordinator.data.get("is_on", False)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0

        speed = self.coordinator.data.get("speed")
        if speed is not None and self._low_high_range:
            return ranged_value_to_percentage(self._low_high_range, speed)
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if not self.is_on:
            return None
        return self.coordinator.data.get("mode")

    @property
    def oscillating(self) -> bool | None:
        """Return oscillation state."""
        if not self.is_on:
            return None
        return self.coordinator.data.get("oscillate")

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        command_params: dict[str, Any] = {"power_switch": True}

        if percentage is not None and percentage > 0 and self._low_high_range:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            command_params["speed"] = speed
        if preset_mode is not None:
            command_params["mode"] = preset_mode

        await self._send_command_and_update(ERROR_TURN_ON_FAILED, **command_params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._send_command_and_update(ERROR_TURN_OFF_FAILED, power_switch=False)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        await self._send_command_and_update(
            ERROR_SET_PRESET_MODE_FAILED, mode=preset_mode
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""
        if percentage <= 0:
            await self.async_turn_off()
        elif self._low_high_range:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            await self._send_command_and_update(ERROR_SET_SPEED_FAILED, speed=speed)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the Oscillate of fan."""
        await self._send_command_and_update(
            ERROR_SET_OSCILLATE_FAILED, oscillate=oscillating
        )
