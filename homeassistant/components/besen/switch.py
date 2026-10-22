"""Switch platform for Besen."""

from datetime import datetime, timedelta
from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenConfigEntry
from .coordinator import BesenCoordinator
from .entity import BesenEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Besen switches."""

    async_add_entities([BesenChargeSwitch(entry.runtime_data)])


class BesenChargeSwitch(BesenEntity, SwitchEntity):
    """Charging control switch."""

    def __init__(self, coordinator: BesenCoordinator) -> None:
        """Initialize the switch."""

        super().__init__(coordinator, "charging")

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether charging is active."""

        return self.coordinator.data.charge.charger_status

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""

        await self.coordinator.async_start_charging()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""

        await self.coordinator.async_stop_charging()

    async def async_start_charging(
        self, start: datetime | None = None, duration: timedelta | None = None
    ) -> None:
        """Start charging at a later time or for a limited time."""

        await self.coordinator.async_start_charging(start, duration)
