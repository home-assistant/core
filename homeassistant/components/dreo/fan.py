"""Support for Dreo fans."""

from __future__ import annotations

from datetime import timedelta
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
from .entity import DreoEntity
from .util import handle_api_exceptions

FAN_SUFFIX = "fan"
SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fan from a config entry."""

    async_add_entities(
        [
            DreoFan(device, config_entry)
            for device in config_entry.runtime_data.devices
            if DEVICE_TYPE.get(device.get("model")) == FAN_DEVICE.get("type")
        ]
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

    def __init__(
        self,
        device: dict[str, Any],
        config_entry: DreoConfigEntry,
    ) -> None:
        """Initialize the Dreo fan."""

        super().__init__(device, config_entry, FAN_SUFFIX, None)

        model_config = FAN_DEVICE.get("config", {}).get(self._model, {})
        speed_range = model_config.get("speed_range")

        self._attr_preset_modes = model_config.get("preset_modes")
        self._attr_preset_mode = None
        self._low_high_range = speed_range
        self._attr_speed_count = int_states_in_range(speed_range)
        self._attr_percentage = None
        self._attr_oscillating = None
        self._attr_is_on = False

    @property
    def is_on(self) -> bool | None:
        """Return True if device is on."""
        return self._attr_is_on

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        command_params: dict[str, Any] = {"power_switch": True}

        if percentage is not None and percentage > 0:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            command_params["speed"] = speed
        if preset_mode is not None:
            command_params["mode"] = preset_mode

        self._send_command(ERROR_TURN_ON_FAILED, **command_params)
        self.schedule_update_ha_state(force_refresh=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._send_command(ERROR_TURN_OFF_FAILED, power_switch=False)
        self.schedule_update_ha_state(force_refresh=True)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        self._send_command(ERROR_SET_PRESET_MODE_FAILED, mode=preset_mode)
        self.schedule_update_ha_state(force_refresh=True)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""
        if percentage <= 0:
            self.turn_off()
        else:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            self._send_command(ERROR_SET_SPEED_FAILED, speed=speed)
            self.schedule_update_ha_state(force_refresh=True)

    def oscillate(self, oscillating: bool) -> None:
        """Set the Oscillate of fan."""
        self._send_command(ERROR_SET_OSCILLATE_FAILED, oscillate=oscillating)
        self.schedule_update_ha_state(force_refresh=True)

    def update(self) -> None:
        """Update Dreo fan."""

        def get_status():
            return self._config_entry.runtime_data.client.get_status(self._device_id)

        status = handle_api_exceptions(get_status)

        if status is None:
            self._attr_available = False
        else:
            self._attr_is_on = status.get("power_switch")
            self._attr_available = status.get("connected")
            self._attr_preset_mode = status.get("mode")
            self._attr_percentage = ranged_value_to_percentage(
                self._low_high_range,
                status.get("speed"),
            )
            self._attr_oscillating = status.get("oscillate")
