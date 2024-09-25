"""Nice G.O. switch platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NiceGOConfigEntry
from .entity import NiceGOEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NiceGOConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nice G.O. switch."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        NiceGOSwitchEntity(coordinator, device_id, device_data.name)
        for device_id, device_data in coordinator.data.items()
    )


class NiceGOSwitchEntity(NiceGOEntity, SwitchEntity):
    """Representation of a Nice G.O. switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "vacation_mode"

    @property
    def is_on(self) -> bool:
        """Return if switch is on."""
        return self.data.vacation_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api.vacation_mode_on(self.data.id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api.vacation_mode_off(self.data.id)
