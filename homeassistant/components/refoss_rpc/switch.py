"""Switch entities for refoss."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RefossConfigEntry, RefossCoordinator
from .entity import RefossEntity
from .utils import get_refoss_key_ids


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch for device."""
    coordinator = config_entry.runtime_data.coordinator
    assert coordinator

    switch_key_ids = get_refoss_key_ids(coordinator.device.status, "switch")

    async_add_entities(RefossSwitch(coordinator, _id) for _id in switch_key_ids)


class RefossSwitch(RefossEntity, SwitchEntity):
    """Refoss switch entity."""

    def __init__(self, coordinator: RefossCoordinator, _id: int) -> None:
        """Initialize  switch."""
        super().__init__(coordinator, f"switch:{_id}")
        self._id = _id

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(self.status["output"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.call_rpc("Switch.Action.Set", {"id": self._id, "action": "on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.call_rpc("Switch.Action.Set", {"id": self._id, "action": "off"})

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle."""
        await self.call_rpc("Switch.Action.Set", {"id": self._id, "action": "toggle"})
