"""Switches for Redfish systems."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RedfishConfigEntry, RedfishDataUpdateCoordinator
from .entity import RedfishSystemEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RedfishConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Redfish switches."""
    async_add_entities(
        RedfishSystemSwitch(entry.runtime_data, system_id)
        for system_id in entry.runtime_data.data.systems
    )


class RedfishSystemSwitch(RedfishSystemEntity, SwitchEntity):
    """A Redfish ComputerSystem power switch."""

    _attr_translation_key = "power"

    def __init__(
        self, coordinator: RedfishDataUpdateCoordinator, system_id: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{self._system_identity}_power"

    @property
    @override
    def is_on(self) -> bool:
        """Return true only for the exact Redfish On state."""
        return self.system is not None and self.system.power_state == "On"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on using only the advertised On action."""
        await self._async_reset("On")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off using only the advertised GracefulShutdown action."""
        await self._async_reset("GracefulShutdown")
