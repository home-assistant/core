"""WiZ integration switch platform."""

from __future__ import annotations

from typing import Any

from pywizlight import PilotBuilder
from pywizlight.bulblibrary import BulbClass

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WizConfigEntry
from .entity import WizToggleEntity
from .models import WizData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WiZ switch platform."""
    if entry.runtime_data.bulb.bulbtype.bulb_type == BulbClass.SOCKET:
        async_add_entities([WizSocketEntity(entry.runtime_data, entry.title)])


class WizSocketEntity(WizToggleEntity, SwitchEntity):
    """Representation of a WiZ socket."""

    _attr_name = None

    def __init__(self, wiz_data: WizData, name: str) -> None:
        """Initialize a WiZ socket."""
        super().__init__(wiz_data, name)
        self._async_update_attrs()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the socket to turn on."""
        await self._device.turn_on(PilotBuilder())
        await self.coordinator.async_request_refresh()
