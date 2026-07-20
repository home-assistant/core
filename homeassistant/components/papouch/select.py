"""Select platform for the Papouch integration."""

from homeassistant.components.select import SelectEntity
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
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = []

    for select_data in device.get_supported_selects():
        entities.append(  # noqa: PERF401
            PapouchCounterSelect(coordinator, entry, select_data["item_id"])
        )

    async_add_entities(entities)


class PapouchCounterSelect(PapouchEntity, SelectEntity):
    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        item_id: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_select_{item_id}"
        self._attr_name = f"Counter {item_id} Mode"
        self._attr_options = coordinator.device.COUNTER_MODES

    @property
    def current_option(self) -> str | None:
        return self.coordinator.device.get_counter_mode(self.item_id)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.device.set_counter_mode(self.item_id, option)
        self.async_write_ha_state()
