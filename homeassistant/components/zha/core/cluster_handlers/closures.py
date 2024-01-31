"""Closures cluster handlers module for Zigbee Home Automation."""
from __future__ import annotations

from typing import Any

import zigpy.types as t
from zigpy.zcl.clusters.closures import ConfigStatus, DoorLock, Shade, WindowCovering

from homeassistant.core import callback

from .. import registries
from ..const import REPORT_CONFIG_IMMEDIATE, SIGNAL_ATTR_UPDATED
from . import AttrReportConfig, ClientClusterHandler, ClusterHandler


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(DoorLock.cluster_id)
class DoorLockClusterHandler(ClusterHandler):
    """Door lock cluster handler."""

    _value_attribute = 0
    REPORT_CONFIG = (
        AttrReportConfig(
            attr=DoorLock.AttributeDefs.lock_state.name,
            config=REPORT_CONFIG_IMMEDIATE,
        ),
    )

    async def async_update(self):
        """Retrieve latest state."""
        result = await self.get_attribute_value(
            DoorLock.AttributeDefs.lock_state.name, from_cache=True
        )
        if result is not None:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                DoorLock.AttributeDefs.lock_state.id,
                DoorLock.AttributeDefs.lock_state.name,
                result,
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

        if command_name == DoorLock.ClientCommandDefs.operation_event_notification.name:
            self.zha_send_event(
                command_name,
                {
                    "source": args[0].name,
                    "operation": args[1].name,
                    "code_slot": (args[2] + 1),  # start code slots at 1
                },
            )

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
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
            DoorLock.UserStatus.Enabled,
            DoorLock.UserType.Unrestricted,
            user_code,
        )

    async def async_enable_user_code(self, code_slot: int) -> None:
        """Enable the code slot."""

        await self.set_user_status(code_slot - 1, DoorLock.UserStatus.Enabled)

    async def async_disable_user_code(self, code_slot: int) -> None:
        """Disable the code slot."""

        await self.set_user_status(code_slot - 1, DoorLock.UserStatus.Disabled)

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


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Shade.cluster_id)
class ShadeClusterHandler(ClusterHandler):
    """Shade cluster handler."""


@registries.CLIENT_CLUSTER_HANDLER_REGISTRY.register(WindowCovering.cluster_id)
class WindowCoveringClientClusterHandler(ClientClusterHandler):
    """Window client cluster handler."""


@registries.BINDABLE_CLUSTERS.register(WindowCovering.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(WindowCovering.cluster_id)
class WindowCoveringClusterHandler(ClusterHandler):
    """Window cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=WindowCovering.AttributeDefs.current_position_lift_percentage.name,
            config=REPORT_CONFIG_IMMEDIATE,
        ),
        AttrReportConfig(
            attr=WindowCovering.AttributeDefs.current_position_tilt_percentage.name,
            config=REPORT_CONFIG_IMMEDIATE,
        ),
    )

    ZCL_INIT_ATTRS = {
        WindowCovering.AttributeDefs.window_covering_type.name: True,
        WindowCovering.AttributeDefs.window_covering_mode.name: True,
        WindowCovering.AttributeDefs.config_status.name: True,
        WindowCovering.AttributeDefs.installed_closed_limit_lift.name: True,
        WindowCovering.AttributeDefs.installed_closed_limit_tilt.name: True,
        WindowCovering.AttributeDefs.installed_open_limit_lift.name: True,
        WindowCovering.AttributeDefs.installed_open_limit_tilt.name: True,
    }

    async def async_update(self):
        """Retrieve latest state."""
        results = await self.get_attributes(
            [
                WindowCovering.AttributeDefs.current_position_lift_percentage.name,
                WindowCovering.AttributeDefs.current_position_tilt_percentage.name,
            ],
            from_cache=False,
            only_cache=False,
        )
        self.debug(
            "read current_position_lift_percentage and current_position_tilt_percentage - results: %s",
            results,
        )
        if (
            results
            and results.get(
                WindowCovering.AttributeDefs.current_position_lift_percentage.name
            )
            is not None
        ):
            # the 100 - value is because we need to invert the value before giving it to the entity
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                WindowCovering.AttributeDefs.current_position_lift_percentage.id,
                WindowCovering.AttributeDefs.current_position_lift_percentage.name,
                100
                - results.get(
                    WindowCovering.AttributeDefs.current_position_lift_percentage.name
                ),
            )
        if (
            results
            and results.get(
                WindowCovering.AttributeDefs.current_position_tilt_percentage.name
            )
            is not None
        ):
            # the 100 - value is because we need to invert the value before giving it to the entity
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                WindowCovering.AttributeDefs.current_position_tilt_percentage.id,
                WindowCovering.AttributeDefs.current_position_tilt_percentage.name,
                100
                - results.get(
                    WindowCovering.AttributeDefs.current_position_tilt_percentage.name
                ),
            )

    @property
    def inverted(self):
        """Return true if the window covering is inverted."""
        config_status = self.cluster.get(
            WindowCovering.AttributeDefs.config_status.name
        )
        return (
            config_status is not None
            and ConfigStatus.Open_up_commands_reversed in ConfigStatus(config_status)
        )

    @property
    def current_position_lift_percentage(self) -> t.uint16_t | None:
        """Return the current lift percentage of the window covering."""
        lift_percentage = self.cluster.get(
            WindowCovering.AttributeDefs.current_position_lift_percentage.name
        )
        if lift_percentage is not None:
            # the 100 - value is because we need to invert the value before giving it to the entity
            lift_percentage = 100 - lift_percentage
        return lift_percentage

    @property
    def current_position_tilt_percentage(self) -> t.uint16_t | None:
        """Return the current tilt percentage of the window covering."""
        tilt_percentage = self.cluster.get(
            WindowCovering.AttributeDefs.current_position_tilt_percentage.name
        )
        if tilt_percentage is not None:
            # the 100 - value is because we need to invert the value before giving it to the entity
            tilt_percentage = 100 - tilt_percentage
        return tilt_percentage

    @property
    def installed_open_limit_lift(self) -> t.uint16_t | None:
        """Return the installed open lift limit of the window covering."""
        return self.cluster.get(
            WindowCovering.AttributeDefs.installed_open_limit_lift.name
        )

    @property
    def installed_closed_limit_lift(self) -> t.uint16_t | None:
        """Return the installed closed lift limit of the window covering."""
        return self.cluster.get(
            WindowCovering.AttributeDefs.installed_closed_limit_lift.name
        )

    @property
    def installed_open_limit_tilt(self) -> t.uint16_t | None:
        """Return the installed open tilt limit of the window covering."""
        return self.cluster.get(
            WindowCovering.AttributeDefs.installed_open_limit_tilt.name
        )

    @property
    def installed_closed_limit_tilt(self) -> t.uint16_t | None:
        """Return the installed closed tilt limit of the window covering."""
        return self.cluster.get(
            WindowCovering.AttributeDefs.installed_closed_limit_tilt.name
        )

    @property
    def window_covering_type(self) -> WindowCovering.WindowCoveringType | None:
        """Return the window covering type."""
        return self.cluster.get(WindowCovering.AttributeDefs.window_covering_type.name)
