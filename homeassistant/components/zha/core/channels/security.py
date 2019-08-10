"""
Security channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from . import ZigbeeChannel
from ..helpers import bind_cluster
from ..const import SIGNAL_ATTR_UPDATED

_LOGGER = logging.getLogger(__name__)


class IASZoneChannel(ZigbeeChannel):
    """Channel for the IASZone Zigbee cluster."""

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            state = args[0] & 3
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                state,
            )
            self.debug("Updated alarm state: %s", state)
        elif command_id == 1:
            self.debug("Enroll requested")
            res = self._cluster.enroll_response(0, 0)
            self._zha_device.hass.async_create_task(res)

    async def async_configure(self):
        """Configure IAS device."""
        # Xiaomi devices don't need this and it disrupts pairing
        if self._zha_device.manufacturer == "LUMI":
            return
        from zigpy.exceptions import DeliveryError

        self.debug("started IASZoneChannel configuration")

        await bind_cluster(self.unique_id, self._cluster)
        ieee = self._cluster.endpoint.device.application.ieee

        try:
            res = await self._cluster.write_attributes({"cie_addr": ieee})
            self.debug(
                "wrote cie_addr: %s to '%s' cluster: %s",
                str(ieee),
                self._cluster.ep_attribute,
                res[0],
            )
        except DeliveryError as ex:
            self.debug(
                "Failed to write cie_addr: %s to '%s' cluster: %s",
                str(ieee),
                self._cluster.ep_attribute,
                str(ex),
            )
        self.debug("%s: finished IASZoneChannel configuration")

        await self.get_attribute_value("zone_type", from_cache=False)

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == 2:
            value = value & 3
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value,
            )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value("zone_status", from_cache=from_cache)
        await self.get_attribute_value("zone_state", from_cache=from_cache)
        await super().async_initialize(from_cache)
