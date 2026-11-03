"""Fan platform for Atomberg."""

from typing import Any, override

from atomberg_api import COMMAND_POWER, COMMAND_SPEED, DEVICE_TYPE_FAN, AtombergDevice

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import FAN_SPEEDS
from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg fans."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtombergFan(coordinator, device)
        for device in coordinator.devices_of_type(DEVICE_TYPE_FAN)
    )


class AtombergFan(AtombergEntity, FanEntity):
    """Representation of an Atomberg fan."""

    _attr_name = None
    _attr_speed_count = len(FAN_SPEEDS)
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
    )

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, device, "fan")

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the fan is on."""
        return bool(self.device_state[COMMAND_POWER])

    @property
    @override
    def percentage(self) -> int | None:
        """Return the speed as a percentage."""
        if not self.is_on:
            return 0
        speed = self.device_state[COMMAND_SPEED]
        if speed not in FAN_SPEEDS:
            return None
        return ordered_list_item_to_percentage(FAN_SPEEDS, speed)

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on, optionally at a given speed."""
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self.is_on:
            await self._async_send({COMMAND_POWER: True}, {COMMAND_POWER: True})
        if percentage is not None:
            await self._async_set_speed(percentage)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._async_send({COMMAND_POWER: False}, {COMMAND_POWER: False})

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed."""
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self.is_on:
            await self._async_send({COMMAND_POWER: True}, {COMMAND_POWER: True})
        await self._async_set_speed(percentage)

    async def _async_set_speed(self, percentage: int) -> None:
        speed = percentage_to_ordered_list_item(FAN_SPEEDS, percentage)
        await self._async_send({COMMAND_SPEED: speed}, {COMMAND_SPEED: speed})
