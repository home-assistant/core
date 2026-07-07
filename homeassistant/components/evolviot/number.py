"""Number platform for EvolvIOT."""

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfRatio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "number"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EvolvIOT numbers."""
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
            entities.append(EvolvIOTBrightnessNumber(coordinator, entity))
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class EvolvIOTBrightnessNumber(EvolvIOTEntity, NumberEntity):
    """EvolvIOT brightness number entity."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE

    @property
    def native_value(self) -> float | None:
        """Return the brightness percentage."""
        attributes = self.backend_state.get("attributes") or {}
        value = attributes.get("brightness", self.backend_state.get("raw_value"))
        if value is None:
            value = self.backend_state.get("state")
        if value in (None, "unknown", "unavailable"):
            return None
        try:
            return max(0, min(100, float(value)))
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set brightness percentage."""
        await self._async_send_command({"brightness": round(max(0, min(100, value)))})
