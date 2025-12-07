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
    _domain_add_entity_callbacks: dict[str, AddConfigEntryEntitiesCallback] = {}

    @classmethod
    def add_add_entities_callback(
        cls, domain: str, cb: AddConfigEntryEntitiesCallback
    ) -> None:
        """Remembers callback to register entities for the given domain."""
        cls._domain_add_entity_callbacks[domain] = cb

    @classmethod
    async def register_entity(cls, entity: HausbusEntity) -> None:
        """Registers entity with the prior remembered callback."""
        cb = cls._domain_add_entity_callbacks.get(entity.get_domain())
        if cb is not None:
            cb([entity])

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

        self._type = "to be overridden"
        self._attr_name = "to be overridden"
        self._attr_unique_id = "to be overridden"

        if channel is not None:
            self._type = channel.__class__.__name__.lower()
            self._attr_name = channel.getName()
            self._attr_unique_id = (
                f"{self._device_id}-{self._type}-{self._objectId.getInstanceId()}"
            )

        self._attr_device_info = device_info
        self._attr_translation_key = self._type
        self._attr_extra_state_attributes = {}
        self._configuration: Any = None
        self._debug_identifier = f"{self._device_id} {self._attr_name}"
        self._unsub_dispatcher: Any = None
        self._domain = domain

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

        # add type information for individual actions
        self.hass.data.setdefault(DOMAIN, {}).setdefault("device_types", {})
        self.hass.data[DOMAIN]["device_types"][self.entity_id] = self.__class__.__name__

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, f"hausbus_update_{self._objectId.getValue()}", self.handle_event
        )

        LOGGER.debug(
            "added_to_hass %s type %s",
            self._debug_identifier,
            self.__class__.__name__,
        )

    async def async_will_remove_from_hass(self):
        """Entity wird entfernt."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def ensure_configuration(self) -> bool:
        """Ensures that the channel configuration is known."""
        if self._configuration:
            return True

        self._channel.getConfiguration()

        try:
            await asyncio.wait_for(self._wait_for_configuration(), timeout=5.0)
        except TimeoutError:
            LOGGER.warning(
                "%s Timeout while waiting for configuration of %s",
                self._debug_identifier,
                self.entity_id,
            )
            return False
        else:
            return True

    async def _wait_for_configuration(self):
        """Waits until configuration is received."""
        while not self._configuration:
            await asyncio.sleep(0.1)
