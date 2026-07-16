"""Number platform for the Papouch integration."""

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .entity import PapouchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Entry for the Home Assistant."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchCounter(coordinator, entry, number_data["item_id"])
        for number_data in device.get_supported_numbers()
    ]
    async_add_entities(entities)


class PapouchCounter(PapouchEntity, NumberEntity):
    """Default counter of the Papouch's device used for decreasing."""

    _attr_native_min_value = 0
    _attr_native_max_value = 2**16 - 1  # TODO: hard-coded
    _attr_native_step = 1

    def __init__(self, coordinator, entry, item_id) -> None:
        """Constructor of the UI counter."""
        super().__init__(coordinator, entry)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_counter_{item_id}"
        self._attr_name = f"Decrease counter {item_id} by: "

    @property
    def native_value(self) -> float | None:
        """Value of the counter."""
        return self.coordinator.data.get("cnt", {}).get(self.item_id)

    async def async_set_native_value(self, value: float) -> None:
        """Setter for the value."""
        value = int(value)
        await self.coordinator.device.decrease_value_counter(self.item_id, value)
        await self.coordinator.async_request_refresh()
