"""Support for push notifications event entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import THINQ_DEVICE_ADDED, ThinqConfigEntry
from .device import LGDevice
from .entity_helpers import (
    ThinQEntity,
    ThinQEntityDescriptionT,
    ThinQEventEntityDescription,
)
from .property import PropertyFeature

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup entry for event platform."""
    _LOGGER.warning("Starting event platform setup...")
    lge_devices: list[LGDevice] = entry.runtime_data.lge_devices

    @callback
    def async_add_devices(devices: list[LGDevice]) -> None:
        """Add event entities."""
        async_add_entities(ThinQEventEntity.create_entities(devices))

    async_add_devices(lge_devices)

    entry.async_on_unload(
        async_dispatcher_connect(hass, THINQ_DEVICE_ADDED, async_add_devices)
    )


class ThinQEventEntity(ThinQEntity[ThinQEventEntityDescription], EventEntity):
    """Represent an thinq event platform."""

    target_platform = Platform.EVENT

    def __init__(
        self,
        device: LGDevice,
        property: property,
        entity_description: ThinQEntityDescriptionT,
    ) -> None:
        """Initialize event platform."""
        super().__init__(device, property, entity_description)

        # For event types.
        self._attr_event_types = self.get_options()

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Handle an event.
        value: Any = self.get_value()
        if value in self._attr_event_types:
            self._async_handle_event(value)
            self._device.noti_message = None

    @callback
    def _async_handle_event(self, event_type: str) -> None:
        """Handle the event."""
        self._trigger_event(event_type=event_type)
        self.async_write_ha_state()
