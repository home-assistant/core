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
from .const import FAN_SUFFIX
from .entity import DreoEntity
from .util import handle_api_exceptions

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fan from a config entry."""

    async_add_entities(
        [
            DreoFanHA(device, config_entry, FAN_SUFFIX)
            for device in config_entry.runtime_data.devices
            if DEVICE_TYPE.get(device.get("model")) == FAN_DEVICE.get("type")
        ]
    )


class DreoFanHA(DreoEntity, FanEntity):
    """Dreo fan."""

    _attr_should_poll = True
    SCAN_INTERVAL = timedelta(seconds=10)

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
        unique_id_suffix: str = "",
    ) -> None:
        """Initialize the Dreo fan."""

        super().__init__(device, config_entry, unique_id_suffix)
        self._attr_name = None

        model_config = FAN_DEVICE.get("config", {}).get(self._model, {})
        speed_range = model_config.get("speed_range")

        self._fan_props = {
            "name": None,
            "state": False,
            "preset_modes": model_config.get("preset_modes"),
            "preset_mode": None,
            "low_high_range": speed_range,
            "speed_count": int_states_in_range(speed_range),
            "percentage": None,
            "oscillating": None,
        }

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        return

    @property
    def is_on(self) -> bool | None:
        """Return True if device is on."""
        return self._fan_props["state"]

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return self._fan_props["preset_modes"]

    @property
    def preset_mode(self) -> str | None:
        """Return the preset mode of the fan."""
        return self._fan_props["preset_mode"]

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._fan_props["speed_count"]

    @property
    def oscillating(self) -> bool | None:
        """Return the oscillate of the fan."""
        return self._fan_props["oscillating"]

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self._fan_props["percentage"]

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        self._send_command("Turn the device on failed.", power_switch=True)
        self._fan_props["state"] = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._send_command("Turn the device off failed.", power_switch=False)
        self._fan_props["state"] = False

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        self._send_command("Set the preset mode failed.", mode=preset_mode)
        self._fan_props["preset_mode"] = preset_mode

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""
        if percentage > 0:
            speed = math.ceil(
                percentage_to_ranged_value(
                    self._fan_props["low_high_range"], percentage
                )
            )
            self._send_command("Set the speed failed.", speed=speed)
        self._fan_props["percentage"] = percentage

    def oscillate(self, oscillating: bool) -> None:
        """Set the Oscillate of fan."""
        self._send_command("Set the Oscillate failed.", oscillate=oscillating)
        self._fan_props["oscillating"] = oscillating

    def update(self) -> None:
        """Update Dreo fan."""

        def get_status():
            return self._config_entry.runtime_data.client.get_status(self._device_id)

        status = handle_api_exceptions(get_status)

        if status is None:
            self._attr_available = False
        else:
            self._fan_props["state"] = status.get("power_switch")
            self._fan_props["preset_mode"] = status.get("mode")
            self._fan_props["percentage"] = ranged_value_to_percentage(
                self._fan_props["low_high_range"],
                status.get("speed"),
            )
            self._fan_props["oscillating"] = status.get("oscillate")
            self._attr_available = status.get("connected")
