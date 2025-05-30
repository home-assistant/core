"""Nice G.O. switch platform."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    KNOWN_UNSUPPORTED_DEVICE_TYPES,
    SUPPORTED_DEVICE_TYPES,
    UNSUPPORTED_DEVICE_WARNING,
)
from .coordinator import NiceGOConfigEntry
from .entity import NiceGOEntity
from .util import retry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NiceGOConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Nice G.O. switch."""
    coordinator = config_entry.runtime_data

    entities = []

    for device_id, device_data in coordinator.data.items():
        if device_data.type in SUPPORTED_DEVICE_TYPES[Platform.SWITCH]:
            entities.append(
                NiceGOSwitchEntity(coordinator, device_id, device_data.name)
            )
        elif device_data.type not in KNOWN_UNSUPPORTED_DEVICE_TYPES[Platform.SWITCH]:
            _LOGGER.warning(
                UNSUPPORTED_DEVICE_WARNING,
                device_data.name,
                device_data.type,
                device_data.type,
            )

    async_add_entities(entities)


class NiceGOSwitchEntity(NiceGOEntity, SwitchEntity):
    """Representation of a Nice G.O. switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "vacation_mode"

    @property
    def is_on(self) -> bool:
        """Return if switch is on."""
        if TYPE_CHECKING:
            assert self.data.vacation_mode is not None
        return self.data.vacation_mode

    @retry("switch_on_error")
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""

        await self.coordinator.api.vacation_mode_on(self.data.id)

    @retry("switch_off_error")
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""

        await self.coordinator.api.vacation_mode_off(self.data.id)
