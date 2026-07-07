"""Select platform for EvolvIOT."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "select"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EvolvIOT selects."""
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
            entities.append(EvolvIOTSelect(coordinator, entity))
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class EvolvIOTSelect(EvolvIOTEntity, SelectEntity):
    """EvolvIOT select entity."""

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = self.backend_state.get("state", self.backend_state.get("raw_value"))
        if value in (None, "", "unknown", "unavailable"):
            return self.options[0] if self.options else None
        return str(value)

    @property
    def options(self) -> list[str]:
        """Return selectable options."""
        attributes = self.backend_state.get("attributes") or {}
        control = self.backend_entity.get("control") or {}
        options = attributes.get("options") or control.get("options")
        if isinstance(options, list) and options:
            return [
                str(option["value"] if isinstance(option, dict) else option)
                for option in options
            ]

        value_list = attributes.get("value_list") or control.get("value_list")
        if isinstance(value_list, list):
            return [str(value) for value in value_list]
        if isinstance(value_list, str):
            return [
                value.strip()
                for value in value_list.split(",")
                if value.strip()
            ]

        return []

    async def async_select_option(self, option: str) -> None:
        """Set EvolvIOT state to the selected option."""
        await self._async_send_command({"value": option})
