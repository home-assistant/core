"""Closures channels module for Zigbee Home Automation."""
from zigpy.exceptions import ZigbeeException
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
    def cluster_command(self, tsn, command_id, args):
        """Handle a cluster command received on this cluster."""

        # Operational Event
        if (
            command_id == 32
            and self._cluster.client_commands is not None
            and self._cluster.client_commands.get(command_id) is not None
            and isinstance(args[0], closures.DoorLock.OperationEventSource)
            and isinstance(args[1], closures.DoorLock.OperationEvent)
        ):
            self.zha_send_event(
                self._cluster.client_commands.get(command_id)[0],
                {
                    "source": args[0].name,
                    "operation": args[1].name,
                    "code_slot": (args[2] + 1),  # start code slots at 1
                },
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

    async def async_set_user_code(self, code_slot: int, user_code: str) -> None:
        """Set the user code for the code slot."""

        try:
            await self.cluster.command(  # returns a response, should probably look at it
                5,  # 0x0005 -> set_pin_code #TODO figure out pulling this out of self.cluster.server_commands
                *(
                    code_slot - 1,  # start code slots at 1
                    closures.DoorLock.UserStatus.Enabled,
                    closures.DoorLock.UserType.Unrestricted,
                    user_code,
                ),
                manufacturer=None,
                expect_reply=True,
            )
        except ZigbeeException as ex:
            self.error("Could not set user code: %s", ex)
            return

    async def async_clear_user_code(self, code_slot: int) -> None:
        """Clear the code slot."""

        try:
            await self.cluster.command(  # returns a response, should probably look at it
                7,  # 0x0007 -> clear_pin_code #TODO figure out pulling this out of self.cluster.server_commands
                *(code_slot - 1,),  # start code slots at 1
                manufacturer=None,
                expect_reply=True,
            )
        except ZigbeeException as ex:
            self.error("Could not clear user code: %s", ex)
            return


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
