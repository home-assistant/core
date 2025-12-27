"""Representation of a Haus-Bus Entity."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.ObjectId import ObjectId

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

LOGGER = logging.getLogger(__name__)


class HausbusEntity(Entity):
    """Common base class for Haus-Bus entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        channel: ABusFeature,
        domain: str,
        device_info: DeviceInfo,
        alternativeType: str | None = None,
    ) -> None:
        """Set up channel."""
        super().__init__()

        self._channel = channel
        self._objectId = ObjectId(channel.getObjectId())
        self._device_id = self._objectId.getDeviceId()
        self._attr_device_info = device_info
        self._attr_translation_key = self._type
        self._attr_extra_state_attributes = {}
        self._configuration: Any = None
        self._debug_identifier = f"{self._device_id} {self._attr_name}"
        self._unsub_dispatcher: Any = None
        self._domain = domain

        if channel is not None:
            self._type = channel.__class__.__name__.lower()
            self._attr_name = channel.getName()
            self._attr_unique_id = (
                f"{self._device_id}-{self._type}-{self._objectId.getInstanceId()}"
            )

    def get_domain(self) -> str:
        """Returns the domain of this entity."""
        return self._domain

    def get_hardware_status(self) -> None:
        """Request status and configuration of this channel from hardware."""
        if self._channel is not None:
            self._channel.getStatus()
            self._channel.getConfiguration()

    def handle_event(self, data: Any) -> None:
        """Handle haus-bus events."""
        LOGGER.debug("handle_event %s for %s", data, self._debug_identifier)

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """State push update."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA."""

        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"hausbus_update_{self._objectId.getValue()}", self.handle_event
        ))
        
        LOGGER.debug(
            "added_to_hass %s type %s",
            self._debug_identifier,
            self.__class__.__name__,
        )
