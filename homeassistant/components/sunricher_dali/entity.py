"""Base entity for Sunricher DALI integration."""

from __future__ import annotations

import logging

from PySrDaliGateway import CallbackEventType, DaliObjectBase, Device

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class DaliCenterEntity(Entity):
    """Base entity for DALI Center objects (devices, scenes, etc.)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, dali_object: DaliObjectBase) -> None:
        """Initialize base entity."""
        self._dali_object = dali_object
        self._attr_unique_id = dali_object.unique_id
        self._unavailable_logged = False
        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Register availability listener."""
        self.async_on_remove(
            self._dali_object.register_listener(
                CallbackEventType.ONLINE_STATUS,
                self._handle_availability,
            )
        )

    @callback
    def _handle_availability(self, available: bool) -> None:
        """Handle availability changes."""
        if not available and not self._unavailable_logged:
            _LOGGER.info("Entity %s became unavailable", self.entity_id)
            self._unavailable_logged = True
        elif available and self._unavailable_logged:
            _LOGGER.info("Entity %s is back online", self.entity_id)
            self._unavailable_logged = False

        self._attr_available = available
        self.schedule_update_ha_state()


class DaliDeviceEntity(DaliCenterEntity):
    """Base entity for DALI Device objects."""

    def __init__(self, device: Device) -> None:
        """Initialize device entity."""
        super().__init__(device)
        self._attr_available = device.status == "online"
