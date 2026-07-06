"""Fan platform for EvolvIOT."""

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "fan"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EvolvIOT fans."""
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
            entities.append(EvolvIOTFan(coordinator, entity))
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class EvolvIOTFan(EvolvIOTEntity, FanEntity):
    """EvolvIOT fan entity."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        state = self.backend_state.get("state")
        if state is None:
            return None
        return str(state).lower() == "on"

    @property
    def percentage(self) -> int | None:
        """Return fan speed percentage."""
        value = self.backend_state.get("attributes", {}).get("percentage")
        if value is None:
            return 100 if self.is_on else 0
        return max(0, min(100, int(value)))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._async_send_command({"command": "turn_on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._async_send_command({"command": "turn_off"})

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        await self._async_send_command({"percentage": max(0, min(100, percentage))})
