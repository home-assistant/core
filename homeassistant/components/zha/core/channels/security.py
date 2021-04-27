"""
Security channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging

from zigpy.exceptions import ZigbeeException
import zigpy.zcl.clusters.security as security
from zigpy.zcl.clusters.security import IasAce as AceCluster

from homeassistant.core import CALLABLE_T, callback

from .. import registries, typing as zha_typing
from ..const import (
    SIGNAL_ATTR_UPDATED,
    WARNING_DEVICE_MODE_EMERGENCY,
    WARNING_DEVICE_SOUND_HIGH,
    WARNING_DEVICE_SQUAWK_MODE_ARMED,
    WARNING_DEVICE_STROBE_HIGH,
    WARNING_DEVICE_STROBE_YES,
)
from .base import ChannelStatus, ZigbeeChannel

IAS_ACE_ARM = 0x0000  # ("arm", (t.enum8, t.CharacterString, t.uint8_t), False),
IAS_ACE_BYPASS = 0x0001  # ("bypass", (t.LVList(t.uint8_t), t.CharacterString), False),
IAS_ACE_EMERGENCY = 0x0002  # ("emergency", (), False),
IAS_ACE_FIRE = 0x0003  # ("fire", (), False),
IAS_ACE_PANIC = 0x0004  # ("panic", (), False),
IAS_ACE_GET_ZONE_ID_MAP = 0x0005  # ("get_zone_id_map", (), False),
IAS_ACE_GET_ZONE_INFO = 0x0006  # ("get_zone_info", (t.uint8_t,), False),
IAS_ACE_GET_PANEL_STATUS = 0x0007  # ("get_panel_status", (), False),
IAS_ACE_GET_BYPASSED_ZONE_LIST = 0x0008  # ("get_bypassed_zone_list", (), False),
IAS_ACE_GET_ZONE_STATUS = (
    0x0009  # ("get_zone_status", (t.uint8_t, t.uint8_t, t.Bool, t.bitmap16), False)
)
NAME = 0
SIGNAL_ARMED_STATE_CHANGED = "zha_armed_state_changed"
SIGNAL_ALARM_TRIGGERED = "zha_armed_triggered"

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(AceCluster.cluster_id)
class IasAce(ZigbeeChannel):
    """IAS Ancillary Control Equipment channel."""

    def __init__(
        self, cluster: zha_typing.ZigpyClusterType, ch_pool: zha_typing.ChannelPoolType
    ) -> None:
        """Initialize IAS Ancillary Control Equipment channel."""
        super().__init__(cluster, ch_pool)
        self.command_map: dict[int, CALLABLE_T] = {
            IAS_ACE_ARM: self.arm,
            IAS_ACE_BYPASS: self._bypass,
            IAS_ACE_EMERGENCY: self._emergency,
            IAS_ACE_FIRE: self._fire,
            IAS_ACE_PANIC: self._panic,
            IAS_ACE_GET_ZONE_ID_MAP: self._get_zone_id_map,
            IAS_ACE_GET_ZONE_INFO: self._get_zone_info,
            IAS_ACE_GET_PANEL_STATUS: self._send_panel_status_response,
            IAS_ACE_GET_BYPASSED_ZONE_LIST: self._get_bypassed_zone_list,
            IAS_ACE_GET_ZONE_STATUS: self._get_zone_status,
        }
        self.arm_map: dict[AceCluster.ArmMode, CALLABLE_T] = {
            AceCluster.ArmMode.Disarm: self._disarm,
            AceCluster.ArmMode.Arm_All_Zones: self._arm_away,
            AceCluster.ArmMode.Arm_Day_Home_Only: self._arm_day,
            AceCluster.ArmMode.Arm_Night_Sleep_Only: self._arm_night,
        }
        self.armed_state: AceCluster.PanelStatus = AceCluster.PanelStatus.Panel_Disarmed
        self.invalid_tries: int = 0

        # These will all be setup by the entity from zha configuration
        self.panel_code: str = "1234"
        self.code_required_arm_actions = False
        self.max_invalid_tries: int = 3

        # where do we store this to handle restarts
        self.alarm_status: AceCluster.AlarmStatus = AceCluster.AlarmStatus.No_Alarm

    @callback
    def cluster_command(self, tsn, command_id, args) -> None:
        """Handle commands received to this cluster."""
        self.warning(
            "received command %s", self._cluster.server_commands.get(command_id)[NAME]
        )
        self.command_map[command_id](*args)

    def arm(self, arm_mode: int, code: str, zone_id: int):
        """Handle the IAS ACE arm command."""
        mode = AceCluster.ArmMode(arm_mode)

        self.zha_send_event(
            self._cluster.server_commands.get(IAS_ACE_ARM)[NAME],
            {
                "arm_mode": mode.value,
                "arm_mode_description": mode.name,
                "code": code,
                "zone_id": zone_id,
            },
        )

        zigbee_reply = self.arm_map[mode](code)
        self._ch_pool.hass.async_create_task(zigbee_reply)

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
            self.warning("Invalid code supplied to IAS ACE")
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
                self.warning("IAS ACE already disarmed")
                zigbee_reply = self.arm_response(
                    AceCluster.ArmNotification.Already_Disarmed
                )
            else:
                self.warning("Disarming all IAS ACE zones")
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
            self.warning("Invalid code supplied to IAS ACE")
            zigbee_reply = self.arm_response(
                AceCluster.ArmNotification.Invalid_Arm_Disarm_Code
            )
        else:
            self.warning("Arming all IAS ACE zones")
            self.armed_state = panel_status
            zigbee_reply = self.arm_response(armed_type)
        return zigbee_reply

    def _bypass(self, zone_list, code) -> None:
        """Handle the IAS ACE bypass command."""
        self.zha_send_event(
            self._cluster.server_commands.get(IAS_ACE_BYPASS)[NAME],
            {"zone_list": zone_list, "code": code},
        )

    def _emergency(self) -> None:
        """Handle the IAS ACE emergency command."""
        self._set_alarm(
            AceCluster.AlarmStatus.Emergency,
            IAS_ACE_EMERGENCY,
        )

    def _fire(self) -> None:
        """Handle the IAS ACE fire command."""
        self._set_alarm(
            AceCluster.AlarmStatus.Fire,
            IAS_ACE_FIRE,
        )

    def _panic(self) -> None:
        """Handle the IAS ACE panic command."""
        self._set_alarm(
            AceCluster.AlarmStatus.Emergency_Panic,
            IAS_ACE_PANIC,
        )

    def _set_alarm(self, status: AceCluster.PanelStatus, event: str) -> None:
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
        self._ch_pool.hass.async_create_task(response)

    def _send_panel_status_changed(self) -> None:
        """Handle the IAS ACE panel status changed command."""
        response = self.panel_status_changed(
            self.armed_state,
            0x00,
            AceCluster.AudibleNotification.Default_Sound,
            self.alarm_status,
        )
        self._ch_pool.hass.async_create_task(response)

    def _get_bypassed_zone_list(self):
        """Handle the IAS ACE bypassed zone list command."""

    def _get_zone_status(
        self, starting_zone_id, max_zone_ids, zone_status_mask_flag, zone_status_mask
    ):
        """Handle the IAS ACE zone status command."""


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

    async def issue_squawk(
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
        except ZigbeeException as ex:
            self.debug(
                "Failed to write cie_addr: %s to '%s' cluster: %s",
                str(ieee),
                self._cluster.ep_attribute,
                str(ex),
            )

        self.debug("Sending pro-active IAS enroll response")
        self._cluster.create_catching_task(self._cluster.enroll_response(0, 0))

        self._status = ChannelStatus.CONFIGURED
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

    def async_initialize_channel_specific(self, from_cache: bool) -> Coroutine:
        """Initialize channel."""
        attributes = ["zone_status", "zone_state", "zone_type"]
        return self.get_attributes(attributes, from_cache=from_cache)
