"""Support for Dreo fans."""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage, int_states_in_range
)
from hscloud.const import FAN_DEVICE

from . import MyConfigEntry
from .entity import DreoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: MyConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Fan from a config entry."""

    async_add_entities([DreoFanHA(device, config_entry) for device in config_entry.runtime_data.fans])


class DreoFanHA(DreoEntity, FanEntity):
    """Dreo fan."""
    _state = False
    _mode = None
    _speed = 0
    _direction = None
    _oscillate = False
    _available = True

    _attr_supported_features = (FanEntityFeature.PRESET_MODE
                                | FanEntityFeature.SET_SPEED
                                | FanEntityFeature.OSCILLATE)

    def __init__(self, device, config_entry) -> None:
        """Initialize the Dreo fan."""
        super().__init__(device, config_entry)

    @property
    def is_on(self) -> bool | None:
        """Return True if device is on."""
        return self._state

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return FAN_DEVICE.get("config").get(self._model).get("preset_modes")

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        return self._mode

    @property
    def speed_count(self) -> int:
        """Get the number of speeds the fan supports."""
        return int_states_in_range(
            FAN_DEVICE.get("config").get(self._model).get("speed_range")
        )

    @property
    def percentage(self) -> int | None:
        """Get the current speed."""
        return ranged_value_to_percentage(
            FAN_DEVICE.get("config").get(self._model).get("speed_range"),
            self._speed
        )

    @property
    def oscillating(self) -> bool | None:
        """Get the current Oscillate."""
        return self._oscillate

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._available

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        result = self._try_command(
            "Turn the device on failed.", power_switch=True
        )

        if result:
            self._state = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        result = self._try_command(
            "Turn the device off failed.", power_switch=False
        )

        if result:
            self._state = False

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        result = self._try_command(
            "Set the preset mode failed.", mode=preset_mode
        )

        if result:
            self._mode = preset_mode

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""
        speed = math.ceil(
            percentage_to_ranged_value(
                FAN_DEVICE.get("config").get(self._model).get("speed_range"), percentage
            )
        )

        if speed == 0:
            return

        result = self._try_command(
            "Set the speed failed.", speed=speed
        )

        if result:
            self._speed = speed

    def oscillate(self, oscillating: bool) -> None:
        """Set the Oscillate of fan."""
        result = self._try_command(
            "Set the Oscillate failed.", oscillate=oscillating
        )

        if result:
            self._oscillate = oscillating

    def update(self) -> None:
        """Update Dreo fan."""
        status = self._config_entry.runtime_data.client.get_status(self._device_id)
        if status is not None:
            self._state = status.get('power_switch')
            self._mode = status.get('mode')
            self._speed = status.get('speed')
            self._oscillate = status.get('oscillate')
            self._available = status.get('connected')
