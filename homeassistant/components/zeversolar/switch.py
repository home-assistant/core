"""Switch platform for Zeversolar — enables/disables inverter output."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MINIMUM_LIMIT
from .coordinator import ZeversolarConfigEntry, ZeversolarCoordinator
from .entity import ZeversolarEntity
from .ramp import async_ramp


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZeversolarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zeversolar switch."""
    coordinator: ZeversolarCoordinator = entry.runtime_data
    async_add_entities([ZeversolarSwitch(coordinator)])


class ZeversolarSwitch(ZeversolarEntity, SwitchEntity):
    """Switch that ramps output to 100% (on) or minimum (off).

    Switch ON  → ramp to 100%
    Switch OFF → ramp to MINIMUM_LIMIT (5%)

    The slider (number entity) follows in real time as the ramp progresses.
    """

    _attr_translation_key = "output_enabled"
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator: ZeversolarCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = (
            f"{coordinator.data['inverter_data'].serial_number}_output_enabled"
        )

    @property
    def available(self) -> bool:
        """Unavailable if API unsupported or a ramp is in progress."""
        return (
            super().available
            and self.coordinator.power_limit_supported
            and not self.coordinator.ramp_lock.locked()
        )

    @property
    def is_on(self) -> bool:
        """True when output is not suppressed to minimum."""
        return self.coordinator.data["power_limit"] > MINIMUM_LIMIT

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Ramp output up to 100%."""
        await self._ramp_to(100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Ramp output down to minimum."""
        await self._ramp_to(MINIMUM_LIMIT)

    async def _ramp_to(self, target: int) -> None:
        if self.coordinator.ramp_lock.locked():
            return

        async def on_step(value: int) -> None:
            self.coordinator.async_set_updated_data(
                {**self.coordinator.data, "power_limit": value}
            )

        async with self.coordinator.ramp_lock:
            # Notify listeners immediately so the switch shows unavailable
            # while the ramp is in progress (availability checks ramp_lock).
            self.coordinator.async_set_updated_data(self.coordinator.data)
            await async_ramp(self.hass, self.coordinator.host, target, on_step)

        await self.coordinator.async_request_refresh()
