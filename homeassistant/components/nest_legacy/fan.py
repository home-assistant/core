"""Fan platform for Nest thermostats."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.models import NestThermostat

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest fan platform from a config entry."""
    coordinator = entry.runtime_data
    entities = [
        NestThermostatFan(coordinator, device)
        for device in coordinator.data.values()
        if isinstance(device, NestThermostat) and device.has_fan
    ]
    async_add_devices(entities)


class NestThermostatFan(NestEntity[NestThermostat], FanEntity):
    """Representation of a Nest Thermostat Fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_translation_key = "fan"

    def __init__(self, coordinator: NestCoordinator, device: NestThermostat) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.serial_number}-fan"
        self._speed_range = (1, device.fan_max_speed)

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self.device.fan_state

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0
        return ranged_value_to_percentage(
            self._speed_range, self.device.fan_timer_speed
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._speed_range)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            # If no percentage is specified, turn on at the last known speed
            await self._set_fan_state(True)
        else:
            speed = round(percentage_to_ranged_value(self._speed_range, percentage))
            if speed == 0:
                speed = 1  # Cannot set speed to 0 when turning on
            await self._set_fan_state(True, speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._set_fan_state(False)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = round(percentage_to_ranged_value(self._speed_range, percentage))
        await self._set_fan_state(True, speed)

    async def _set_fan_state(self, fan_on: bool, speed: int | None = None) -> None:
        """Set the fan state."""
        timeout = (
            int(dt_util.utcnow().timestamp()) + self.device.fan_duration
            if fan_on
            else 0
        )
        payload: dict[str, Any] = {"fan_timer_timeout": timeout}
        if fan_on and speed is not None:
            payload["fan_timer_speed"] = f"stage{speed}"
        await self._set_device_data(payload)
