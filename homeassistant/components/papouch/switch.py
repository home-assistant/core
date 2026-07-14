"""Switch platform for the Papouch integration."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data
    entities = []

    # TODO: refaktor into new class
    for item_id in coordinator.data.get("dout", {}):
        entities.append(PapouchSwitch(coordinator, entry, item_id))

    async_add_entities(entities)


class PapouchSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Quido relay/output."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        item_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_out_{item_id}"
        self._attr_name = f"Output {item_id}"
        self._attr_device_info = {
            "identifiers": {(entry.domain, entry.entry_id)},
            "name": "Papouch Quido",
            "manufacturer": "Papouch s.r.o.",
        }

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        val = self.coordinator.data.get("dout", {}).get(self.item_id)
        return val == 1 if val is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api_client.send_command("s", self.item_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api_client.send_command("r", self.item_id)
        await self.coordinator.async_request_refresh()
