"""Support for Dreo fans."""
from __future__ import annotations

import logging
import math
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage, int_states_in_range
)
from .const import DOMAIN, MANAGER, FAN_DEVICE, FAN_CONFIG
from .device import DreoEntity
from typing import Any

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Fan from a config entry."""

    devices = hass.data[DOMAIN][config_entry.entry_id].get(FAN_DEVICE)

    fans = [DreoFanHA(device.get("deviceName"), device, config_entry, device.get("deviceSn")) for device in devices]

    async_add_entities(fans)


class DreoFanHA(DreoEntity, FanEntity):
    """Dreo fan."""

    _attr_supported_features = (FanEntityFeature.PRESET_MODE
                                | FanEntityFeature.SET_SPEED
                                | FanEntityFeature.OSCILLATE)
    _attr_name = None

    def __init__(self, name, device, entry, unique_id) -> None:
        """Initialize the Dreo fan."""
        super().__init__(name, device, entry, unique_id)

        self._state = False
        self._mode = None
        self._speed = 0
        self._direction = None
        self._oscillate = False
        self._available = True

    @property
    def is_on(self) -> bool | None:
        """Return True if device is on."""
        return self._state

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return FAN_CONFIG.get(self._model).get("preset_modes")

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        return self._mode

    @property
    def speed_count(self) -> int:
        """Get the number of speeds the fan supports."""
        return int_states_in_range(
            FAN_CONFIG.get(self._model).get("speed_range")
        )

    @property
    def percentage(self) -> int | None:
        """Get the current speed."""
        return ranged_value_to_percentage(
            FAN_CONFIG.get(self._model).get("speed_range"),
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
            self.async_write_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        result = self._try_command(
            "Turn the device off failed.", power_switch=False
        )

        if result:
            self._state = False
            self.async_write_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        result = self._try_command(
            "Set the preset mode failed.", mode=preset_mode
        )

        if result:
            self._mode = preset_mode
            self.async_write_ha_state()

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""
        speed = math.ceil(
            percentage_to_ranged_value(
                FAN_CONFIG.get(self._model).get("speed_range"), percentage
            )
        )

        if speed == 0:
            return

        result = self._try_command(
            "Set the speed failed.", speed=speed
        )

        if result:
            self._speed = speed
            self.async_write_ha_state()

    def oscillate(self, oscillating: bool) -> None:
        """Set the Oscillate of fan."""
        result = self._try_command(
            "Set the Oscillate failed.", oscillate=oscillating
        )

        if result:
            self._oscillate = oscillating
            self.async_write_ha_state()

    def update(self) -> None:
        """Update Dreo fan."""
        _entry_id = self._config_entry.entry_id
        manager = self.hass.data[DOMAIN][_entry_id].get(MANAGER)

        status = manager.get_status(self._device_id)
        if status is not None:
            self._state = status.get('power_switch')
            self._mode = status.get('mode')
            self._speed = status.get('speed')
            self._oscillate = status.get('oscillate')
            self._available = status.get('connected')
