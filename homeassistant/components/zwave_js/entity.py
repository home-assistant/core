"""Generic Z-Wave Entity Class."""

import logging

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .discovery import ZwaveDiscoveryInfo

LOGGER = logging.getLogger(__name__)

EVENT_VALUE_UPDATED = "value updated"


class ZWaveBaseEntity(Entity):
    """Generic Entity Class for a Z-Wave Device."""

    def __init__(self, client: ZwaveClient, info: ZwaveDiscoveryInfo):
        """Initialize a generic Z-Wave device entity."""
        self.client = client
        self.info = info
        # entities requiring additional values, can add extra properties to this list
        self.watched_values = [self.info.primary_value.property_]

    @callback
    def on_value_update(self):
        """Call when one of the watched values change.

        To be overridden by platforms needing this event.
        """

    async def async_added_to_hass(self):
        """Call when entity is added."""
        # Add value_changed callbacks.
        self.async_on_remove(
            # TODO: only subscribe to values we're interested in (requires change in library)
            self.info.node.on(EVENT_VALUE_UPDATED, self._value_changed)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update_{self.info.discovery_id}", self._value_changed
            )
        )

    @property
    def device_info(self) -> dict:
        """Return device information for the device registry."""
        # device is precreated in main handler
        return {
            "identifiers": {
                (DOMAIN, self.client.driver.controller.home_id, self.info.node.node_id)
            },
        }

    @property
    def name(self) -> str:
        """Return default name from device name and value name combination."""
        node_name = self.info.node.name or self.info.node.device_config.description
        return f"{node_name}: {self.info.primary_value.property_name}"

    @property
    def unique_id(self) -> str:
        """Return the unique_id of the entity."""
        return f"{self.client.driver.controller.home_id}.{self.info.discovery_id}"

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.client.connected and self.info.node.ready

    @callback
    def _value_changed(self, event_data: dict):
        """Call when (one of) our watched values changes.

        Should not be overridden by subclasses.
        """
        if event_data["args"]["property"] in self.watched_values:
            self.on_value_update()
            self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False
