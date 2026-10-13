"""Representation of a Haus-Bus Entity."""

import logging
from typing import Any, override

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.ObjectId import ObjectId

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)


class HausbusEntity(Entity):
    """Common base class for Haus-Bus entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        channel: ABusFeature,
        device_info: DeviceInfo,
    ) -> None:
        """Set up channel."""
        super().__init__()

        self._channel = channel

        self._object_id = ObjectId(channel.getObjectId())
        self._device_id = self._object_id.getDeviceId()
        self._type = channel.__class__.__name__.lower()

        self._attr_device_info = device_info
        # The channel name is configured on the Haus-Bus hardware itself, so
        # it is used as-is rather than through a translation_key.
        self._attr_name = channel.getName()
        self._attr_unique_id = (
            f"{self._device_id}-{self._type}-{self._object_id.getInstanceId()}"
        )
        self._debug_identifier = f"{self._device_id} {self._attr_name}"

    def get_hardware_status(self) -> None:
        """Request status from hardware."""
        self._channel.getStatus()

    @callback
    def handle_event(self, data: Any) -> None:
        """Handle haus-bus events.

        Must stay marked @callback: unmarked, the dispatcher would run this
        (and subclass overrides) in the executor instead of the event loop.
        """
        LOGGER.debug("handle_event %s for %s", data, self._debug_identifier)

    @override
    async def async_added_to_hass(self) -> None:
        """Register for haus-bus updates once entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"hausbus_update_{self._object_id.getValue()}",
                self.handle_event,
            )
        )

        # Request the current status only once this entity is listening for
        # the response, and off the event loop since it sends blocking UDP traffic.
        await self.hass.async_add_executor_job(self.get_hardware_status)

        LOGGER.debug(
            "added_to_hass %s type %s",
            self._debug_identifier,
            self.__class__.__name__,
        )
