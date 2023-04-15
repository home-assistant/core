"""Closures cluster handlers module for Zigbee Home Automation."""
from zigpy.zcl.clusters import closures

from homeassistant.core import callback

from . import AttrReportConfig, ClientClusterHandler, ClusterHandler
from .. import registries
from ..const import REPORT_CONFIG_IMMEDIATE, SIGNAL_ATTR_UPDATED


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(closures.DoorLock.cluster_id)
class DoorLockClusterHandler(ClusterHandler):
    """Door lock cluster handler."""

    _value_attribute = 0
    REPORT_CONFIG = (
        AttrReportConfig(attr="lock_state", config=REPORT_CONFIG_IMMEDIATE),
    )

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

        if (
            self._cluster.client_commands is None
            or self._cluster.client_commands.get(command_id) is None
        ):
            return

        command_name = self._cluster.client_commands[command_id].name

        if command_name == "operation_event_notification":
            self.zha_send_event(
                command_name,
                {
                    "source": args[0].name,
                    "operation": args[1].name,
                    "code_slot": (args[2] + 1),  # start code slots at 1
                },
            )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from lock cluster."""
        attr_name = self._get_attribute_name(attrid)
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attrid == self._value_attribute:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, attr_name, value
            )

    async def async_set_user_code(self, code_slot: int, user_code: str) -> None:
        """Set the user code for the code slot."""

        await self.set_pin_code(
            code_slot - 1,  # start code slots at 1, Zigbee internals use 0
            closures.DoorLock.UserStatus.Enabled,
            closures.DoorLock.UserType.Unrestricted,
            user_code,
        )

    async def async_enable_user_code(self, code_slot: int) -> None:
        """Enable the code slot."""

        await self.set_user_status(code_slot - 1, closures.DoorLock.UserStatus.Enabled)

    async def async_disable_user_code(self, code_slot: int) -> None:
        """Disable the code slot."""

        await self.set_user_status(code_slot - 1, closures.DoorLock.UserStatus.Disabled)

    async def async_get_user_code(self, code_slot: int) -> int:
        """Get the user code from the code slot."""

        result = await self.get_pin_code(code_slot - 1)
        return result

    async def async_clear_user_code(self, code_slot: int) -> None:
        """Clear the code slot."""

        await self.clear_pin_code(code_slot - 1)

    async def async_clear_all_user_codes(self) -> None:
        """Clear all code slots."""

        await self.clear_all_pin_codes()

    async def async_set_user_type(self, code_slot: int, user_type: str) -> None:
        """Set user type."""

        await self.set_user_type(code_slot - 1, user_type)

    async def async_get_user_type(self, code_slot: int) -> str:
        """Get user type."""

        result = await self.get_user_type(code_slot - 1)
        return result


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(closures.Shade.cluster_id)
class Shade(ClusterHandler):
    """Shade cluster handler."""


@registries.CLIENT_CLUSTER_HANDLER_REGISTRY.register(closures.WindowCovering.cluster_id)
class WindowCoveringClient(ClientClusterHandler):
    """Window client cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(closures.WindowCovering.cluster_id)
class WindowCovering(ClusterHandler):
    """Window cluster handler."""

    _value_attribute = 8
    REPORT_CONFIG = (
        AttrReportConfig(
            attr="current_position_lift_percentage", config=REPORT_CONFIG_IMMEDIATE
        ),
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
        attr_name = self._get_attribute_name(attrid)
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attrid == self._value_attribute:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, attr_name, value
            )
