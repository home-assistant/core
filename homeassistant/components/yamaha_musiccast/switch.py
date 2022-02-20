"""The switch entities for musiccast."""
from typing import Any

from aiomusiccast.capabilities import BinarySetter

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, MusicCastCapabilityEntity, MusicCastDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    switch_entities = []

    for capability in coordinator.data.capabilities:
        if isinstance(capability, BinarySetter):
            switch_entities.append(SwitchCapability(coordinator, capability))

    for zone, data in coordinator.data.zones.items():
        for capability in data.capabilities:
            if isinstance(capability, BinarySetter):
                switch_entities.append(SwitchCapability(coordinator, capability, zone))

    async_add_entities(switch_entities)


class SwitchCapability(MusicCastCapabilityEntity, SwitchEntity):
    """Representation of a MusicCast switch entity."""

    capability: BinarySetter

    @property
    def is_on(self) -> bool:
        """Return the current status."""
        return self.capability.current

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the capability."""
        await self.capability.set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the capability."""
        await self.capability.set(False)
