"""Base Entity for Trinnov Altitude."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import AREA, DOMAIN, MANUFACTURER, MODEL, NAME

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from trinnov_altitude.messages import Message
    from trinnov_altitude.trinnov_altitude import TrinnovAltitude

_LOGGER = logging.getLogger(__name__)


class TrinnovAltitudeEntity(Entity):
    """Defines a base Trinnov Altitude entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: TrinnovAltitude) -> None:
        """Initialize entity."""

        self._device = device
        self._callback: Callable[[Any], None] | None = None

        self._attr_unique_id = device.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.id))},
            # Instead of setting the device name to the entity name,
            # this should be updated to set has_entity_name = True
            name=f"{NAME} ({device.id})",
            model=MODEL,
            manufacturer=MANUFACTURER,
            sw_version=f"{device.version}",
            suggested_area=AREA,
            configuration_url=f"http://{device.host}",
        )

    async def async_added_to_hass(self) -> None:
        """Register update listener."""

        @callback
        def _update(event: Message) -> None:
            """Handle device state changes."""
            self.async_write_ha_state()

        self._callback = _update
        self._device.register_callback(self._callback)

    async def async_will_remove_from_hass(self):
        """Deregister update listener."""

        if self._callback is not None:
            self._device.deregister_callback(self._callback)
