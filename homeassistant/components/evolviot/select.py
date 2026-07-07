"""Select platform for EvolvIOT."""

from typing import Any

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

    def __init__(
        self,
        coordinator: EvolvIOTDataUpdateCoordinator,
        entity: dict[str, Any],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, entity)
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        options = self.options
        state_value = self.backend_state.get("state")
        raw_value = self.backend_state.get("raw_value")
        value = raw_value if state_value in (None, "", "unknown", "unavailable") else state_value

        if value in (None, "", "unknown", "unavailable"):
            if self._optimistic_option in options:
                return self._optimistic_option
            return options[0] if options else None

        option = _option_from_value(value, options)
        if option is not None:
            return option
        if self._optimistic_option in options:
            return self._optimistic_option
        return None

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
        self._optimistic_option = option
        self.async_write_ha_state()


def _option_from_value(value: Any, options: list[str]) -> str | None:
    """Return a select option from a backend state value."""
    value_string = str(value)
    if value_string in options:
        return value_string

    try:
        option_index = int(value_string)
    except ValueError:
        return None

    if 0 <= option_index < len(options):
        return options[option_index]
    return None
