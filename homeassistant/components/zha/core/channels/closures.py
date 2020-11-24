"""Closures channels module for Zigbee Home Automation."""
import zigpy.zcl.clusters.closures as closures

from homeassistant.core import callback

from .. import registries
from ..const import REPORT_CONFIG_IMMEDIATE, SIGNAL_ATTR_UPDATED
from .base import ClientChannel, ZigbeeChannel


@registries.ZIGBEE_CHANNEL_REGISTRY.register(closures.DoorLock.cluster_id)
class DoorLockChannel(ZigbeeChannel):
    """Door lock channel."""

    _value_attribute = 0
    REPORT_CONFIG = ({"attr": "lock_state", "config": REPORT_CONFIG_IMMEDIATE},)

    async def async_update(self):
        """Retrieve latest state."""
        result = await self.get_attribute_value("lock_state", from_cache=True)
        if result is not None:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", 0, "lock_state", result
            )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from lock cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attrid == self._value_attribute:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, attr_name, value
            )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(self._value_attribute, from_cache=from_cache)
        await super().async_initialize(from_cache)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(closures.Shade.cluster_id)
class Shade(ZigbeeChannel):
    """Shade channel."""


@registries.CLIENT_CHANNELS_REGISTRY.register(closures.WindowCovering.cluster_id)
class WindowCoveringClient(ClientChannel):
    """Window client channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(closures.WindowCovering.cluster_id)
class WindowCovering(ZigbeeChannel):
    """Window channel."""

    _value_attribute = 8
    REPORT_CONFIG = (
        {"attr": "current_position_lift_percentage", "config": REPORT_CONFIG_IMMEDIATE},
    )

    async def async_update(self):
        """Retrieve latest state."""
        result = await self.get_attribute_value(
            "current_position_lift_percentage", from_cache=False
        )
        self.debug("read current position: %s", result)
        if result is not None:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                8,
                "current_position_lift_percentage",
                result,
            )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from window_covering cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attrid == self._value_attribute:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, attr_name, value
            )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(self._value_attribute, from_cache=from_cache)
        await super().async_initialize(from_cache)
