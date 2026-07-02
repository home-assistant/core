"""Switch platform for Besen BS20."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenBS20ConfigEntry
from .coordinator import BesenBS20Coordinator
from .entity import BesenBS20Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Besen BS20 switches."""

    async_add_entities([BesenBS20ChargeSwitch(entry.runtime_data)])


class BesenBS20ChargeSwitch(BesenBS20Entity, SwitchEntity):
    """Charging control switch."""

    def __init__(self, coordinator: BesenBS20Coordinator) -> None:
        """Initialize the switch."""

        super().__init__(coordinator, "charging")

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether charging is active."""

        data = self.coordinator.data or self.coordinator.client.state
        return data.charge.charger_status

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""

        await self.coordinator.async_start_charging()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""

        await self.coordinator.async_stop_charging()
