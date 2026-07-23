"""Switch platform for the Papouch integration."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchSwitch(coordinator, entry, switch_data)
        for switch_data in device.get_supported_switches()
    ]

    async_add_entities(entities)


class PapouchSwitch(PapouchEntity, SwitchEntity):
    """Representation of a unified Papouch switch entity."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        switch_data: dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self.item_id = switch_data["item_id"]
        self._attr_unique_id = f"{entry.entry_id}_{'switch'}_{self.item_id}"
        self._attr_name = switch_data["name"]

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        val = self.coordinator.data.get("switch", {}).get(self.item_id)
        return val == 1 if val is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.device.turn_on_switch(self.item_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.device.turn_off_switch(self.item_id)
        await self.coordinator.async_request_refresh()
