"""Security cluster handlers module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import zigpy.zcl
from zigpy.zcl.clusters.security import IasAce as AceCluster, IasWd, IasZone

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .. import registries
from ..const import (
    SIGNAL_ATTR_UPDATED,
    WARNING_DEVICE_MODE_EMERGENCY,
    WARNING_DEVICE_SOUND_HIGH,
    WARNING_DEVICE_SQUAWK_MODE_ARMED,
    WARNING_DEVICE_STROBE_HIGH,
    WARNING_DEVICE_STROBE_YES,
)
from . import ClusterHandler, ClusterHandlerStatus

if TYPE_CHECKING:
    from ..endpoint import Endpoint

SIGNAL_ARMED_STATE_CHANGED = "zha_armed_state_changed"
SIGNAL_ALARM_TRIGGERED = "zha_armed_triggered"


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AceCluster.cluster_id)
class IasAceClusterHandler(ClusterHandler):
    """IAS Ancillary Control Equipment cluster handler."""

    def __init__(self, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> None:
        """Initialize IAS Ancillary Control Equipment cluster handler."""
        super().__init__(cluster, endpoint)
        self.command_map: dict[int, Callable[..., Any]] = {
            AceCluster.ServerCommandDefs.arm.id: self.arm,
            AceCluster.ServerCommandDefs.bypass.id: self._bypass,
            AceCluster.ServerCommandDefs.emergency.id: self._emergency,
            AceCluster.ServerCommandDefs.fire.id: self._fire,
            AceCluster.ServerCommandDefs.panic.id: self._panic,
            AceCluster.ServerCommandDefs.get_zone_id_map.id: self._get_zone_id_map,
            AceCluster.ServerCommandDefs.get_zone_info.id: self._get_zone_info,
            AceCluster.ServerCommandDefs.get_panel_status.id: self._send_panel_status_response,
            AceCluster.ServerCommandDefs.get_bypassed_zone_list.id: self._get_bypassed_zone_list,
            AceCluster.ServerCommandDefs.get_zone_status.id: self._get_zone_status,
        }
        self.arm_map: dict[AceCluster.ArmMode, Callable[..., Any]] = {
            AceCluster.ArmMode.Disarm: self._disarm,
            AceCluster.ArmMode.Arm_All_Zones: self._arm_away,
            AceCluster.ArmMode.Arm_Day_Home_Only: self._arm_day,
            AceCluster.ArmMode.Arm_Night_Sleep_Only: self._arm_night,
        }
        self.armed_state: AceCluster.PanelStatus = AceCluster.PanelStatus.Panel_Disarmed
        self.invalid_tries: int = 0

        # These will all be setup by the entity from ZHA configuration
        self.panel_code: str = "1234"
        self.code_required_arm_actions = False
        self.max_invalid_tries: int = 3

        # where do we store this to handle restarts
        self.alarm_status: AceCluster.AlarmStatus = AceCluster.AlarmStatus.No_Alarm

    @callback
    def cluster_command(self, tsn, command_id, args) -> None:
        """Handle commands received to this cluster."""
        self.debug(
            "received command %s", self._cluster.server_commands[command_id].name
        )
        self.command_map[command_id](*args)

    def arm(self, arm_mode: int, code: str | None, zone_id: int) -> None:
        """Handle the IAS ACE arm command."""
        mode = AceCluster.ArmMode(arm_mode)

        self.zha_send_event(
            AceCluster.ServerCommandDefs.arm.name,
            {
                "arm_mode": mode.value,
                "arm_mode_description": mode.name,
                "code": code,
                "zone_id": zone_id,
            },
        )

        zigbee_reply = self.arm_map[mode](code)
        self._endpoint.device.hass.async_create_task(zigbee_reply)

        if self.invalid_tries >= self.max_invalid_tries:
            self.alarm_status = AceCluster.AlarmStatus.Emergency
            self.armed_state = AceCluster.PanelStatus.In_Alarm
            self.async_send_signal(f"{self.unique_id}_{SIGNAL_ALARM_TRIGGERED}")
        else:
            self.async_send_signal(f"{self.unique_id}_{SIGNAL_ARMED_STATE_CHANGED}")
        self._send_panel_status_changed()

    def _disarm(self, code: str):
        """Test the code and disarm the panel if the code is correct."""
        if (
            code != self.panel_code
            and self.armed_state != AceCluster.PanelStatus.Panel_Disarmed
        ):
            self.debug("Invalid code supplied to IAS ACE")
            self.invalid_tries += 1
            zigbee_reply = self.arm_response(
                AceCluster.ArmNotification.Invalid_Arm_Disarm_Code
            )
        else:
            self.invalid_tries = 0
            if (
                self.armed_state == AceCluster.PanelStatus.Panel_Disarmed
                and self.alarm_status == AceCluster.AlarmStatus.No_Alarm
            ):
                self.debug("IAS ACE already disarmed")
                zigbee_reply = self.arm_response(
                    AceCluster.ArmNotification.Already_Disarmed
                )
            else:
                self.debug("Disarming all IAS ACE zones")
                zigbee_reply = self.arm_response(
                    AceCluster.ArmNotification.All_Zones_Disarmed
                )

            self.armed_state = AceCluster.PanelStatus.Panel_Disarmed
            self.alarm_status = AceCluster.AlarmStatus.No_Alarm
        return zigbee_reply

    def _arm_day(self, code: str) -> None:
        """Arm the panel for day / home zones."""
        return self._handle_arm(
            code,
            AceCluster.PanelStatus.Armed_Stay,
            AceCluster.ArmNotification.Only_Day_Home_Zones_Armed,
        )

    def _arm_night(self, code: str) -> None:
        """Arm the panel for night / sleep zones."""
        return self._handle_arm(
            code,
            AceCluster.PanelStatus.Armed_Night,
            AceCluster.ArmNotification.Only_Night_Sleep_Zones_Armed,
        )

    def _arm_away(self, code: str) -> None:
        """Arm the panel for away mode."""
        return self._handle_arm(
            code,
            AceCluster.PanelStatus.Armed_Away,
            AceCluster.ArmNotification.All_Zones_Armed,
        )

    def _handle_arm(
        self,
        code: str,
        panel_status: AceCluster.PanelStatus,
        armed_type: AceCluster.ArmNotification,
    ) -> None:
        """Arm the panel with the specified statuses."""
        if self.code_required_arm_actions and code != self.panel_code:
            self.debug("Invalid code supplied to IAS ACE")
            zigbee_reply = self.arm_response(
                AceCluster.ArmNotification.Invalid_Arm_Disarm_Code
            )
        else:
            self.debug("Arming all IAS ACE zones")
            self.armed_state = panel_status
            zigbee_reply = self.arm_response(armed_type)
        return zigbee_reply

    def _bypass(self, zone_list, code) -> None:
        """Handle the IAS ACE bypass command."""
        self.zha_send_event(
            AceCluster.ServerCommandDefs.bypass.name,
            {"zone_list": zone_list, "code": code},
        )

    def _emergency(self) -> None:
        """Handle the IAS ACE emergency command."""
        self._set_alarm(AceCluster.AlarmStatus.Emergency)

    def _fire(self) -> None:
        """Handle the IAS ACE fire command."""
        self._set_alarm(AceCluster.AlarmStatus.Fire)

    def _panic(self) -> None:
        """Handle the IAS ACE panic command."""
        self._set_alarm(AceCluster.AlarmStatus.Emergency_Panic)

    def _set_alarm(self, status: AceCluster.AlarmStatus) -> None:
        """Set the specified alarm status."""
        self.alarm_status = status
        self.armed_state = AceCluster.PanelStatus.In_Alarm
        self.async_send_signal(f"{self.unique_id}_{SIGNAL_ALARM_TRIGGERED}")
        self._send_panel_status_changed()

    def _get_zone_id_map(self):
        """Handle the IAS ACE zone id map command."""

    def _get_zone_info(self, zone_id):
        """Handle the IAS ACE zone info command."""

    def _send_panel_status_response(self) -> None:
        """Handle the IAS ACE panel status response command."""
        response = self.panel_status_response(
            self.armed_state,
            0x00,
            AceCluster.AudibleNotification.Default_Sound,
            self.alarm_status,
        )
        self._endpoint.device.hass.async_create_task(response)

    def _send_panel_status_changed(self) -> None:
        """Handle the IAS ACE panel status changed command."""
        response = self.panel_status_changed(
            self.armed_state,
            0x00,
            AceCluster.AudibleNotification.Default_Sound,
            self.alarm_status,
        )
        self._endpoint.device.hass.async_create_task(response)

    def _get_bypassed_zone_list(self):
        """Handle the IAS ACE bypassed zone list command."""

    def _get_zone_status(
        self, starting_zone_id, max_zone_ids, zone_status_mask_flag, zone_status_mask
    ):
        """Handle the IAS ACE zone status command."""


@registries.CLUSTER_HANDLER_ONLY_CLUSTERS.register(IasWd.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(IasWd.cluster_id)
class IasWdClusterHandler(ClusterHandler):
    """IAS Warning Device cluster handler."""

    @staticmethod
    def set_bit(destination_value, destination_bit, source_value, source_bit):
        """Set the specified bit in the value."""

        if IasWdClusterHandler.get_bit(source_value, source_bit):
            return destination_value | (1 << destination_bit)
        return destination_value

    @staticmethod
    def get_bit(value, bit):
        """Get the specified bit from the value."""
        return (value & (1 << bit)) != 0

    async def issue_squawk(
        self,
        mode=WARNING_DEVICE_SQUAWK_MODE_ARMED,
        strobe=WARNING_DEVICE_STROBE_YES,
        squawk_level=WARNING_DEVICE_SOUND_HIGH,
    ):
        """Issue a squawk command.

        This command uses the WD capabilities to emit a quick audible/visible
        pulse called a "squawk". The squawk command has no effect if the WD
        is currently active (warning in progress).
        """
        value = 0
        value = IasWdClusterHandler.set_bit(value, 0, squawk_level, 0)
        value = IasWdClusterHandler.set_bit(value, 1, squawk_level, 1)

        value = IasWdClusterHandler.set_bit(value, 3, strobe, 0)

        value = IasWdClusterHandler.set_bit(value, 4, mode, 0)
        value = IasWdClusterHandler.set_bit(value, 5, mode, 1)
        value = IasWdClusterHandler.set_bit(value, 6, mode, 2)
        value = IasWdClusterHandler.set_bit(value, 7, mode, 3)

        await self.squawk(value)

    async def issue_start_warning(
        self,
        mode=WARNING_DEVICE_MODE_EMERGENCY,
        strobe=WARNING_DEVICE_STROBE_YES,
        siren_level=WARNING_DEVICE_SOUND_HIGH,
        warning_duration=5,  # seconds
        strobe_duty_cycle=0x00,
        strobe_intensity=WARNING_DEVICE_STROBE_HIGH,
    ):
        """Issue a start warning command.

        This command starts the WD operation. The WD alerts the surrounding area
        by audible (siren) and visual (strobe) signals.

        strobe_duty_cycle indicates the length of the flash cycle. This provides a means
        of varying the flash duration for different alarm types (e.g., fire, police,
        burglar). Valid range is 0-100 in increments of 10. All other values SHALL
        be rounded to the nearest valid value. Strobe SHALL calculate duty cycle over
        a duration of one second.

        The ON state SHALL precede the OFF state. For example, if Strobe Duty Cycle
        Field specifies “40,” then the strobe SHALL flash ON for 4/10ths of a second
        and then turn OFF for 6/10ths of a second.
        """
        value = 0
        value = IasWdClusterHandler.set_bit(value, 0, siren_level, 0)
        value = IasWdClusterHandler.set_bit(value, 1, siren_level, 1)

        value = IasWdClusterHandler.set_bit(value, 2, strobe, 0)

        value = IasWdClusterHandler.set_bit(value, 4, mode, 0)
        value = IasWdClusterHandler.set_bit(value, 5, mode, 1)
        value = IasWdClusterHandler.set_bit(value, 6, mode, 2)
        value = IasWdClusterHandler.set_bit(value, 7, mode, 3)

        await self.start_warning(
            value, warning_duration, strobe_duty_cycle, strobe_intensity
        )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(IasZone.cluster_id)
class IASZoneClusterHandler(ClusterHandler):
    """Cluster handler for the IASZone Zigbee cluster."""

    ZCL_INIT_ATTRS = {
        IasZone.AttributeDefs.zone_status.name: False,
        IasZone.AttributeDefs.zone_state.name: True,
        IasZone.AttributeDefs.zone_type.name: True,
    }

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == IasZone.ClientCommandDefs.status_change_notification.id:
            zone_status = args[0]
            # update attribute cache with new zone status
            self.cluster.update_attribute(
                IasZone.AttributeDefs.zone_status.id, zone_status
            )
            self.debug("Updated alarm state: %s", zone_status)
        elif command_id == IasZone.ClientCommandDefs.enroll.id:
            self.debug("Enroll requested")
            self._cluster.create_catching_task(
                self.enroll_response(
                    enroll_response_code=IasZone.EnrollResponse.Success, zone_id=0
                )
            )

    async def async_configure(self):
        """Configure IAS device."""
        await self.get_attribute_value(
            IasZone.AttributeDefs.zone_type.name, from_cache=False
        )
        if self._endpoint.device.skip_configuration:
            self.debug("skipping IASZoneClusterHandler configuration")
            return

        self.debug("started IASZoneClusterHandler configuration")

        await self.bind()
        ieee = self.cluster.endpoint.device.application.state.node_info.ieee

        try:
            await self.write_attributes_safe(
                {IasZone.AttributeDefs.cie_addr.name: ieee}
            )
            self.debug(
                "wrote cie_addr: %s to '%s' cluster",
                str(ieee),
                self._cluster.ep_attribute,
            )
        except HomeAssistantError as ex:
            self.debug(
                "Failed to write cie_addr: %s to '%s' cluster: %s",
                str(ieee),
                self._cluster.ep_attribute,
                str(ex),
            )

        self.debug("Sending pro-active IAS enroll response")
        self._cluster.create_catching_task(
            self.enroll_response(
                enroll_response_code=IasZone.EnrollResponse.Success, zone_id=0
            )
        )

        self._status = ClusterHandlerStatus.CONFIGURED
        self.debug("finished IASZoneClusterHandler configuration")

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
        """Handle attribute updates on this cluster."""
        if attrid == IasZone.AttributeDefs.zone_status.id:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                attrid,
                IasZone.AttributeDefs.zone_status.name,
                value,
            )
