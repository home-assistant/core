"""Support for Velux switches."""

from __future__ import annotations

from typing import Any

from pyvlx import OnOffSwitch

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .entity import VeluxEntity, wrap_pyvlx_call_exceptions

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch(es) for Velux platform."""
    pyvlx = config_entry.runtime_data
    async_add_entities(
        VeluxOnOffSwitch(node, config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, OnOffSwitch)
    )


class VeluxOnOffSwitch(VeluxEntity, SwitchEntity):
    """Representation of a Velux on/off switch."""

    _attr_name = None

    node: OnOffSwitch

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.node.is_on()

    @wrap_pyvlx_call_exceptions
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.node.set_on()

    @wrap_pyvlx_call_exceptions
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.node.set_off()
