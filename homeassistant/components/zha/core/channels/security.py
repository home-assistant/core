"""
Security channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import asyncio
import logging

from zigpy.exceptions import DeliveryError
import zigpy.zcl.clusters.security as security

from homeassistant.core import callback

from .. import registries
from ..const import (
    SIGNAL_ATTR_UPDATED,
    WARNING_DEVICE_MODE_EMERGENCY,
    WARNING_DEVICE_SOUND_HIGH,
    WARNING_DEVICE_SQUAWK_MODE_ARMED,
    WARNING_DEVICE_STROBE_HIGH,
    WARNING_DEVICE_STROBE_YES,
)
from .base import ZigbeeChannel

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(security.IasAce.cluster_id)
class IasAce(ZigbeeChannel):
    """IAS Ancillary Control Equipment channel."""

    pass


@registries.CHANNEL_ONLY_CLUSTERS.register(security.IasWd.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(security.IasWd.cluster_id)
class IasWd(ZigbeeChannel):
    """IAS Warning Device channel."""

    @staticmethod
    def set_bit(destination_value, destination_bit, source_value, source_bit):
        """Set the specified bit in the value."""

        if IasWd.get_bit(source_value, source_bit):
            return destination_value | (1 << destination_bit)
        return destination_value

    @staticmethod
    def get_bit(value, bit):
        """Get the specified bit from the value."""
        return (value & (1 << bit)) != 0

    async def squawk(
        self,
        mode=WARNING_DEVICE_SQUAWK_MODE_ARMED,
        strobe=WARNING_DEVICE_STROBE_YES,
        squawk_level=WARNING_DEVICE_SOUND_HIGH,
    ):
        """Issue a squawk command.

        This command uses the WD capabilities to emit a quick audible/visible pulse called a
        "squawk". The squawk command has no effect if the WD is currently active
        (warning in progress).
        """
        value = 0
        value = IasWd.set_bit(value, 0, squawk_level, 0)
        value = IasWd.set_bit(value, 1, squawk_level, 1)

        value = IasWd.set_bit(value, 3, strobe, 0)

        value = IasWd.set_bit(value, 4, mode, 0)
        value = IasWd.set_bit(value, 5, mode, 1)
        value = IasWd.set_bit(value, 6, mode, 2)
        value = IasWd.set_bit(value, 7, mode, 3)

        await self.squawk(value)

    async def start_warning(
        self,
        mode=WARNING_DEVICE_MODE_EMERGENCY,
        strobe=WARNING_DEVICE_STROBE_YES,
        siren_level=WARNING_DEVICE_SOUND_HIGH,
        warning_duration=5,  # seconds
        strobe_duty_cycle=0x00,
        strobe_intensity=WARNING_DEVICE_STROBE_HIGH,
    ):
        """Issue a start warning command.

        This command starts the WD operation. The WD alerts the surrounding area by audible
        (siren) and visual (strobe) signals.

        strobe_duty_cycle indicates the length of the flash cycle. This provides a means
        of varying the flash duration for different alarm types (e.g., fire, police, burglar).
        Valid range is 0-100 in increments of 10. All other values SHALL be rounded to the
        nearest valid value. Strobe SHALL calculate duty cycle over a duration of one second.
        The ON state SHALL precede the OFF state. For example, if Strobe Duty Cycle Field specifies
        “40,” then the strobe SHALL flash ON for 4/10ths of a second and then turn OFF for
        6/10ths of a second.
        """
        value = 0
        value = IasWd.set_bit(value, 0, siren_level, 0)
        value = IasWd.set_bit(value, 1, siren_level, 1)

        value = IasWd.set_bit(value, 2, strobe, 0)

        value = IasWd.set_bit(value, 4, mode, 0)
        value = IasWd.set_bit(value, 5, mode, 1)
        value = IasWd.set_bit(value, 6, mode, 2)
        value = IasWd.set_bit(value, 7, mode, 3)

        await self.start_warning(
            value, warning_duration, strobe_duty_cycle, strobe_intensity
        )


@registries.BINARY_SENSOR_CLUSTERS.register(security.IasZone.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(security.IasZone.cluster_id)
class IASZoneChannel(ZigbeeChannel):
    """Channel for the IASZone Zigbee cluster."""

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            state = args[0] & 3
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", 2, "zone_status", state
            )
            self.debug("Updated alarm state: %s", state)
        elif command_id == 1:
            self.debug("Enroll requested")
            res = self._cluster.enroll_response(0, 0)
            asyncio.create_task(res)

    async def async_configure(self):
        """Configure IAS device."""
        await self.get_attribute_value("zone_type", from_cache=False)
        if self._ch_pool.skip_configuration:
            self.debug("skipping IASZoneChannel configuration")
            return

        self.debug("started IASZoneChannel configuration")

        await self.bind()
        ieee = self.cluster.endpoint.device.application.ieee

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
        self.debug("finished IASZoneChannel configuration")

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == 2:
            value = value & 3
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                attrid,
                self.cluster.attributes.get(attrid, [attrid])[0],
                value,
            )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        attributes = ["zone_status", "zone_state"]
        await self.get_attributes(attributes, from_cache=from_cache)
        await super().async_initialize(from_cache)
