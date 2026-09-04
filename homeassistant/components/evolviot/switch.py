"""Switch platform for EvolvIOT."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "switch"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EvolvIOT switches."""
    coordinator: EvolvIOTDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        EvolvIOTSwitch(coordinator, entity)
        for entity in coordinator.entities_for_domain(PLATFORM_DOMAIN)
    )


class EvolvIOTSwitch(EvolvIOTEntity, SwitchEntity):
    """EvolvIOT switch entity."""

    _attr_has_entity_name = True

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        state = self.backend_state
        if state is None:
            return None
        return state.is_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_send_command("turn_on")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_send_command("turn_off")
