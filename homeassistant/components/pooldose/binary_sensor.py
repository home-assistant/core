"""Pooldose binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSOR_MAP


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose binary sensors from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []
    for uid, (name, key) in BINARY_SENSOR_MAP.items():
        entities.append(PooldoseBinarySensor(coordinator, api, name, uid, key))
    async_add_entities(entities)


class PooldoseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Pooldose binary sensor."""

    def __init__(self, coordinator, api, name, uid, key) -> None:
        """Initialize a Pooldose binary sensor."""
        super().__init__(coordinator)
        self._api = api
        self._attr_name = name
        self._attr_unique_id = uid
        self._attr_should_poll = False
        self._key = key

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on, False if off, or None if unknown."""
        try:
            return self.coordinator.data["devicedata"][self._api.serial_key][self._key]
        except (KeyError, TypeError):
            return None
