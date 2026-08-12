"""Select platform for the Papouch integration."""

from typing import Any, override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Papouch select platform."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = []

    for select_data in device.get_supported_selects():
        entities.append(PapouchSelectEntity(coordinator, entry, select_data))  # noqa: PERF401

    async_add_entities(entities)


class PapouchSelectEntity(PapouchEntity, SelectEntity):
    """Representation of a unified Papouch select entity."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        select_data: dict[str, Any],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, entry)

        mac = format_mac(coordinator.device.mac_address)

        self.item_id = select_data["item_id"]
        self.category = select_data["category"]

        self._attr_unique_id = f"{mac}_{self.category}_{self.item_id}"
        self._attr_name = select_data["name"]
        self._attr_options = select_data["options"]

        if "icon" in select_data:
            self._attr_icon = select_data["icon"]

    @override
    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self.coordinator.device.get_select_option(self.category, self.item_id)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option on the device."""
        await self.coordinator.device.set_select_option(
            self.category, self.item_id, option
        )
        self.coordinator.async_set_updated_data(self.coordinator.data)
