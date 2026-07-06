"""Binary sensor platform for EvolvIOT."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "binary_sensor"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EvolvIOT binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: EvolvIOTDataUpdateCoordinator = data[DATA_COORDINATOR]
    known = data[DATA_KNOWN_ENTITIES].setdefault(PLATFORM_DOMAIN, set())

    def add_new_entities() -> None:
        entities = []
        for entity in coordinator.entities_for_domain(PLATFORM_DOMAIN):
            entity_id = entity["entity_id"]
            if entity_id in known:
                continue
            known.add(entity_id)
            entities.append(EvolvIOTBinarySensor(coordinator, entity))
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class EvolvIOTBinarySensor(EvolvIOTEntity, BinarySensorEntity):
    """EvolvIOT binary sensor entity."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        state = self.backend_state.get("state")
        if state is None:
            return None
        return str(state).lower() == "on"
