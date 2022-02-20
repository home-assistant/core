"""Support for SleepIQ switches."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from asyncsleepiq import SleepIQBed

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DOMAIN
from .coordinator import SleepIQDataUpdateCoordinator
from .entity import SleepIQEntity

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sleep number switches."""
    coordinator: SleepIQDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SleepNumberPrivateSwitch(bed) for bed in coordinator.client.beds.values()
    )


class SleepNumberPrivateSwitch(SleepIQEntity, SwitchEntity):
    """Representation of SleepIQ privacy mode."""

    def __init__(self, bed: SleepIQBed) -> None:
        """Initialize the switch."""
        super().__init__(bed)
        self._attr_name = f"SleepNumber {bed.name} Pause Mode"
        self._attr_unique_id = f"{bed.id}-pause-mode"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on or off."""
        return bool(self.bed.paused)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.bed.set_pause_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.bed.set_pause_mode(False)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs: Any) -> None:
        """Get the latest data from the SleepIQ API."""
        await self.bed.fetch_pause_mode()
