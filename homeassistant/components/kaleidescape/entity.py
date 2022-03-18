"""Base Entity for Kaleidescape."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN as KALEIDESCAPE_DOMAIN, NAME as KALEIDESCAPE_NAME

if TYPE_CHECKING:
    from kaleidescape import Device as KaleidescapeDevice

_LOGGER = logging.getLogger(__name__)


class KaleidescapeEntity(Entity):
    """Defines a base Kaleidescape entity."""

    def __init__(self, device: KaleidescapeDevice) -> None:
        """Initialize entity."""
        self._device = device

        self._attr_should_poll = False
        self._attr_unique_id = device.serial_number
        self._attr_name = f"{KALEIDESCAPE_NAME} {device.system.friendly_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(KALEIDESCAPE_DOMAIN, self._device.serial_number)},
            name=self.name,
            model=self._device.system.type,
            manufacturer=KALEIDESCAPE_NAME,
            sw_version=f"{self._device.system.kos_version}",
            suggested_area="Theater",
            configuration_url=f"http://{self._device.host}",
        )

    async def async_added_to_hass(self) -> None:
        """Register update listener."""

        @callback
        def _update(event: str) -> None:
            """Handle device state changes."""
            self.async_write_ha_state()

        self.async_on_remove(self._device.dispatcher.connect(_update).disconnect)
