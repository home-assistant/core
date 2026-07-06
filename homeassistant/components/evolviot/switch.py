"""Switch platform for EvolvIOT."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "switch"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EvolvIOT switches."""
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
            entities.append(EvolvIOTSwitch(coordinator, entity))
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class EvolvIOTSwitch(EvolvIOTEntity, SwitchEntity):
    """EvolvIOT switch entity."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        state = self.backend_state.get("state")
        if state is None:
            return None
        return str(state).lower() == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_send_command({"command": "turn_on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_send_command({"command": "turn_off"})
