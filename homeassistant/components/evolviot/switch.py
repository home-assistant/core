"""Switch platform for EvolvIOT."""

from typing import Any, override

from pyevolviot import EvolvIOTEntity as EvolvIOTEntityModel

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EvolvIOTConfigEntry
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

SWITCHES: dict[tuple[str, str], SwitchEntityDescription] = {
    ("switch", "power"): SwitchEntityDescription(key="power"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EvolvIOTConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EvolvIOT switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        EvolvIOTSwitch(
            coordinator,
            entity,
            SWITCHES[(entity.device.model.casefold(), entity.control.key.casefold())],
        )
        for entity in coordinator.entities.values()
        if (entity.device.model.casefold(), entity.control.key.casefold()) in SWITCHES
    )


class EvolvIOTSwitch(EvolvIOTEntity, SwitchEntity):
    """EvolvIOT switch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvolvIOTDataUpdateCoordinator,
        entity: EvolvIOTEntityModel,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entity)
        self.entity_description = description
        self._attr_name = None

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
