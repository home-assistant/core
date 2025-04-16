"""Support for Dreo fans."""

from __future__ import annotations

from datetime import timedelta
import logging
import math
from typing import Any

from hscloud.const import DEVICE_TYPE, FAN_DEVICE
from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudException

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

FAN_SUFFIX = "fan"
SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fan from a config entry."""

    client = config_entry.runtime_data.client

    async_add_entities(
        [
            DreoFan(device, client)
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
        client: HsCloud,
    ) -> None:
        """Initialize the Dreo fan."""

        super().__init__(device, client, FAN_SUFFIX, None)

        model_config = FAN_DEVICE.get("config", {}).get(self._model, {})
        speed_range = model_config.get("speed_range")

        self._attr_preset_modes = model_config.get("preset_modes")
        self._attr_preset_mode = None
        self._low_high_range = speed_range
        self._attr_speed_count = int_states_in_range(speed_range)
        self._attr_percentage = 0
        self._attr_oscillating = None

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

        self._send_command_and_update(ERROR_TURN_ON_FAILED, **command_params)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._send_command_and_update(ERROR_TURN_OFF_FAILED, power_switch=False)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        self._send_command_and_update(ERROR_SET_PRESET_MODE_FAILED, mode=preset_mode)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""
        if percentage <= 0:
            self.turn_off()
        else:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            self._send_command_and_update(ERROR_SET_SPEED_FAILED, speed=speed)

    def oscillate(self, oscillating: bool) -> None:
        """Set the oscillation of fan."""
        self._send_command_and_update(ERROR_SET_OSCILLATE_FAILED, oscillate=oscillating)

    def update(self) -> None:
        """Get updated data from the device."""
        try:
            status = self._client.get_status(self._device_id)

            if status is None:
                self._attr_available = False
                return

            self._attr_available = status.get("connected")

            if not status.get("power_switch"):
                self._attr_percentage = 0
                self._attr_preset_mode = None
                self._attr_oscillating = None
            else:
                self._attr_preset_mode = status.get("mode")
                self._attr_oscillating = status.get("oscillate")
                self._attr_percentage = ranged_value_to_percentage(
                    self._low_high_range,
                    status.get("speed"),
                )
        except (HsCloudException, Exception):
            self._attr_available = False
            _LOGGER.exception("Error getting status for Dreo fan %s", self._device_id)
