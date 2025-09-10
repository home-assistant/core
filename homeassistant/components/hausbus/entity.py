"""Representation of a Haus-Bus Entity."""

from __future__ import annotations

import asyncio
from typing import Any

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.ObjectId import ObjectId

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from .device import HausbusDevice

DOMAIN = "hausbus"

import logging

LOGGER = logging.getLogger(__name__)


class HausbusEntity(Entity):
    """Common base class for Haus-Bus entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        channel: ABusFeature,
        device: HausbusDevice,
        alternativeType: str | None = None,
    ) -> None:
        """Set up channel."""
        super().__init__()

        self._channel = channel
        self._device = device

        self._type = "to be overridden"
        self._attr_name = "to be overridden"
        self._attr_unique_id = "to be overridden"

        if channel is not None:
            self._type = channel.__class__.__name__.lower()
            self._attr_name = channel.getName()
            self._attr_unique_id = f"{self._device.device_id}-{self._type}-{ObjectId(channel.getObjectId()).getInstanceId()}"

        if alternativeType is not None:
            self._type = alternativeType

        self._attr_device_info = self._device.device_info
        self._attr_translation_key = self._type
        self._attr_extra_state_attributes = {}
        self._configuration = {}
        self._special_type = device.special_type

    def get_hardware_status(self) -> None:
        """Request status and configuration of this channel from hardware."""
        if self._channel is not None:
            self._channel.getStatus()
            self._channel.getConfiguration()

    def handle_event(self, data: Any) -> None:
        """Handle haus-bus events."""

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """State push update."""
        raise NotImplementedError

    async def async_added_to_hass(self):
        """Called when entity is added to HA."""
        registry = er.async_get(self.hass)
        registry.async_update_entity_options(
            self.entity_id, DOMAIN, {"hausbus_type": self.__class__.__name__}
        )
        if self._special_type != 0:
            registry.async_update_entity_options(
                self.entity_id, DOMAIN, {"hausbus_special_type": self._special_type}
            )
        LOGGER.debug(
            f"added_to_hass {self._attr_name} type {self.__class__.__name__} special_type {self._special_type}"
        )

    async def ensure_configuration(self) -> bool:
        """Ensures that the channel configuration is known"""
        if self._configuration:
            return True

        self._channel.getConfiguration()

        try:
            await asyncio.wait_for(self._wait_for_configuration(), timeout=5.0)
            return True
        except TimeoutError:
            LOGGER.warning(
                "Timeout while waiting for configuration of %s", self.entity_id
            )
            return False

    async def _wait_for_configuration(self):
        """Waits until configuration is received"""
        while not self._configuration:
            await asyncio.sleep(0.1)
