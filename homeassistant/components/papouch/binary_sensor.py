"""Binary sensor platform for the Papouch integration."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .entity import PapouchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data
    entities = []

    for item_id in coordinator.data.get("din", {}):
        entities.append(PapouchBinarySensor(coordinator, entry, item_id))  # noqa: PERF401

    async_add_entities(entities)


class PapouchBinarySensor(PapouchEntity, BinarySensorEntity):
    """Representation of a digital input as a binary sensor."""

    def __init__(self, coordinator, entry, item_id) -> None:
        """Constructor for binary sensor."""
        super().__init__(coordinator, entry)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_din_{item_id}"
        self._attr_name = f"Input {item_id}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.get("din", {}).get(self.item_id) == 1
