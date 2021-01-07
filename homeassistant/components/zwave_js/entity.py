"""Generic Z-Wave Entity Class."""

import logging

from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue
from zwave_js_server.client import Client as ZwaveClient

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PLATFORMS
from .discovery import ZwaveDiscoveryInfo

LOGGER = logging.getLogger(__name__)


class ZWaveBaseEntity(Entity):
    """Generic Entity Class for a Z-Wave Device."""

    def __init__(self, client: ZwaveClient, info: ZwaveDiscoveryInfo):
        """Initialize a generic Z-Wave device entity."""
        self.client = client
        self.info = info

    @callback
    def on_value_update(self):
        """Call when one of the watched values change.

        To be overridden by platforms needing this event.
        """

    async def async_added_to_hass(self):
        """Call when entity is added."""
        # Add dispatcher and value_changed callbacks.
        # Add to on_remove so they will be cleaned up on entity removal.
        # TODO !
        # self.async_on_remove(
        #     self.options.listen(EVENT_VALUE_CHANGED, self._value_changed)
        # )

    @property
    def device_info(self) -> dict:
        """Return device information for the device registry."""
        # TODO

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        # TODO: Create default name from device name and value name combination
        # return f"{create_device_name(self.info.node)}: {self.info.primary_value.label}"

    @property
    def unique_id(self) -> str:
        """Return the unique_id of the entity."""
        return self.info.value_id

    @property
    def available(self) -> bool:
        """Return entity availability."""
        # TODO: return availability from both client connection state and node ready

    @callback
    def _value_changed(self, value: ZwaveValue):
        """Call when (one of) our watched values changes.

        Should not be overridden by subclasses.
        """
        self.on_value_update()
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False
