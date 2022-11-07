"""General channels module for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

import zigpy.exceptions
import zigpy.types as t
import zigpy.zcl
from zigpy.zcl.clusters import general
from zigpy.zcl.foundation import Status

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from .. import registries
from ..const import (
    REPORT_CONFIG_ASAP,
    REPORT_CONFIG_BATTERY_SAVE,
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_MOVE_LEVEL,
    SIGNAL_SET_LEVEL,
    SIGNAL_UPDATE_DEVICE,
)
from .base import AttrReportConfig, ClientChannel, ZigbeeChannel, parse_and_log_command
from .helpers import is_hue_motion_sensor

if TYPE_CHECKING:
    from . import ChannelPool


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Alarms.cluster_id)
class Alarms(ZigbeeChannel):
    """Alarms channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.AnalogInput.cluster_id)
class AnalogInput(ZigbeeChannel):
    """Analog Input channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.BINDABLE_CLUSTERS.register(general.AnalogOutput.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.AnalogOutput.cluster_id)
class AnalogOutput(ZigbeeChannel):
    """Analog Output channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )
    ZCL_INIT_ATTRS = {
        "min_present_value": True,
        "max_present_value": True,
        "resolution": True,
        "relinquish_default": True,
        "description": True,
        "engineering_units": True,
        "application_type": True,
    }

    @property
    def present_value(self) -> float | None:
        """Return cached value of present_value."""
        return self.cluster.get("present_value")

    @property
    def min_present_value(self) -> float | None:
        """Return cached value of min_present_value."""
        return self.cluster.get("min_present_value")

    @property
    def max_present_value(self) -> float | None:
        """Return cached value of max_present_value."""
        return self.cluster.get("max_present_value")

    @property
    def resolution(self) -> float | None:
        """Return cached value of resolution."""
        return self.cluster.get("resolution")

    @property
    def relinquish_default(self) -> float | None:
        """Return cached value of relinquish_default."""
        return self.cluster.get("relinquish_default")

    @property
    def description(self) -> str | None:
        """Return cached value of description."""
        return self.cluster.get("description")

    @property
    def engineering_units(self) -> int | None:
        """Return cached value of engineering_units."""
        return self.cluster.get("engineering_units")

    @property
    def application_type(self) -> int | None:
        """Return cached value of application_type."""
        return self.cluster.get("application_type")

    async def async_set_present_value(self, value: float) -> bool:
        """Update present_value."""
        try:
            res = await self.cluster.write_attributes({"present_value": value})
        except zigpy.exceptions.ZigbeeException as ex:
            self.error("Could not set value: %s", ex)
            return False
        if not isinstance(res, Exception) and all(
            record.status == Status.SUCCESS for record in res[0]
        ):
            return True
        return False


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.AnalogValue.cluster_id)
class AnalogValue(ZigbeeChannel):
    """Analog Value channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.ApplianceControl.cluster_id)
class ApplianceContorl(ZigbeeChannel):
    """Appliance Control channel."""


@registries.CHANNEL_ONLY_CLUSTERS.register(general.Basic.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Basic.cluster_id)
class BasicChannel(ZigbeeChannel):
    """Channel to interact with the basic cluster."""

    UNKNOWN = 0
    BATTERY = 3
    BIND: bool = False

    POWER_SOURCES = {
        UNKNOWN: "Unknown",
        1: "Mains (single phase)",
        2: "Mains (3 phase)",
        BATTERY: "Battery",
        4: "DC source",
        5: "Emergency mains constantly powered",
        6: "Emergency mains and transfer switch",
    }

    def __init__(self, cluster: zigpy.zcl.Cluster, ch_pool: ChannelPool) -> None:
        """Initialize Basic channel."""
        super().__init__(cluster, ch_pool)
        if is_hue_motion_sensor(self) and self.cluster.endpoint.endpoint_id == 2:
            self.ZCL_INIT_ATTRS = (  # pylint: disable=invalid-name
                self.ZCL_INIT_ATTRS.copy()
            )
            self.ZCL_INIT_ATTRS["trigger_indicator"] = True
        elif (
            self.cluster.endpoint.manufacturer == "TexasInstruments"
            and self.cluster.endpoint.model == "ti.router"
        ):
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["transmit_power"] = True


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.BinaryInput.cluster_id)
class BinaryInput(ZigbeeChannel):
    """Binary Input channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.BinaryOutput.cluster_id)
class BinaryOutput(ZigbeeChannel):
    """Binary Output channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.BinaryValue.cluster_id)
class BinaryValue(ZigbeeChannel):
    """Binary Value channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Commissioning.cluster_id)
class Commissioning(ZigbeeChannel):
    """Commissioning channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.DeviceTemperature.cluster_id)
class DeviceTemperature(ZigbeeChannel):
    """Device Temperature channel."""

    REPORT_CONFIG = (
        {
            "attr": "current_temperature",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        },
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.GreenPowerProxy.cluster_id)
class GreenPowerProxy(ZigbeeChannel):
    """Green Power Proxy channel."""

    BIND: bool = False


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Groups.cluster_id)
class Groups(ZigbeeChannel):
    """Groups channel."""

    BIND: bool = False


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Identify.cluster_id)
class Identify(ZigbeeChannel):
    """Identify channel."""

    BIND: bool = False

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(self, tsn, command_id, args)

        if cmd == "trigger_effect":
            self.async_send_signal(f"{self.unique_id}_{cmd}", args[0])


@registries.CLIENT_CHANNELS_REGISTRY.register(general.LevelControl.cluster_id)
class LevelControlClientChannel(ClientChannel):
    """LevelControl client cluster."""


@registries.BINDABLE_CLUSTERS.register(general.LevelControl.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.LevelControl.cluster_id)
class LevelControlChannel(ZigbeeChannel):
    """Channel for the LevelControl Zigbee cluster."""

    CURRENT_LEVEL = 0
    REPORT_CONFIG = (AttrReportConfig(attr="current_level", config=REPORT_CONFIG_ASAP),)
    ZCL_INIT_ATTRS = {
        "on_off_transition_time": True,
        "on_level": True,
        "on_transition_time": True,
        "off_transition_time": True,
        "default_move_rate": True,
        "start_up_current_level": True,
    }

    @property
    def current_level(self) -> int | None:
        """Return cached value of the current_level attribute."""
        return self.cluster.get("current_level")

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(self, tsn, command_id, args)

        if cmd in ("move_to_level", "move_to_level_with_on_off"):
            self.dispatch_level_change(SIGNAL_SET_LEVEL, args[0])
        elif cmd in ("move", "move_with_on_off"):
            # We should dim slowly -- for now, just step once
            rate = args[1]
            if args[0] == 0xFF:
                rate = 10  # Should read default move rate
            self.dispatch_level_change(SIGNAL_MOVE_LEVEL, -rate if args[0] else rate)
        elif cmd in ("step", "step_with_on_off"):
            # Step (technically may change on/off)
            self.dispatch_level_change(
                SIGNAL_MOVE_LEVEL, -args[1] if args[0] else args[1]
            )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        self.debug("received attribute: %s update with value: %s", attrid, value)
        if attrid == self.CURRENT_LEVEL:
            self.dispatch_level_change(SIGNAL_SET_LEVEL, value)

    def dispatch_level_change(self, command, level):
        """Dispatch level change."""
        self.async_send_signal(f"{self.unique_id}_{command}", level)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.MultistateInput.cluster_id)
class MultistateInput(ZigbeeChannel):
    """Multistate Input channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.MultistateOutput.cluster_id)
class MultistateOutput(ZigbeeChannel):
    """Multistate Output channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.MultistateValue.cluster_id)
class MultistateValue(ZigbeeChannel):
    """Multistate Value channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="present_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.CLIENT_CHANNELS_REGISTRY.register(general.OnOff.cluster_id)
class OnOffClientChannel(ClientChannel):
    """OnOff client channel."""


@registries.BINDABLE_CLUSTERS.register(general.OnOff.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.OnOff.cluster_id)
class OnOffChannel(ZigbeeChannel):
    """Channel for the OnOff Zigbee cluster."""

    ON_OFF = 0
    REPORT_CONFIG = (AttrReportConfig(attr="on_off", config=REPORT_CONFIG_IMMEDIATE),)
    ZCL_INIT_ATTRS = {
        "start_up_on_off": True,
    }

    def __init__(self, cluster: zigpy.zcl.Cluster, ch_pool: ChannelPool) -> None:
        """Initialize OnOffChannel."""
        super().__init__(cluster, ch_pool)
        self._off_listener = None

        if self.cluster.endpoint.model in (
            "TS011F",
            "TS0121",
            "TS0001",
            "TS0002",
            "TS0003",
            "TS0004",
        ):
            self.ZCL_INIT_ATTRS = (  # pylint: disable=invalid-name
                self.ZCL_INIT_ATTRS.copy()
            )
            self.ZCL_INIT_ATTRS["backlight_mode"] = True
            self.ZCL_INIT_ATTRS["power_on_state"] = True

    @property
    def on_off(self) -> bool | None:
        """Return cached value of on/off attribute."""
        return self.cluster.get("on_off")

    async def turn_on(self) -> bool:
        """Turn the on off cluster on."""
        result = await self.on()
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return False
        self.cluster.update_attribute(self.ON_OFF, t.Bool.true)
        return True

    async def turn_off(self) -> bool:
        """Turn the on off cluster off."""
        result = await self.off()
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return False
        self.cluster.update_attribute(self.ON_OFF, t.Bool.false)
        return True

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(self, tsn, command_id, args)

        if cmd in ("off", "off_with_effect"):
            self.cluster.update_attribute(self.ON_OFF, t.Bool.false)
        elif cmd in ("on", "on_with_recall_global_scene"):
            self.cluster.update_attribute(self.ON_OFF, t.Bool.true)
        elif cmd == "on_with_timed_off":
            should_accept = args[0]
            on_time = args[1]
            # 0 is always accept 1 is only accept when already on
            if should_accept == 0 or (should_accept == 1 and bool(self.on_off)):
                if self._off_listener is not None:
                    self._off_listener()
                    self._off_listener = None
                self.cluster.update_attribute(self.ON_OFF, t.Bool.true)
                if on_time > 0:
                    self._off_listener = async_call_later(
                        self._ch_pool.hass,
                        (on_time / 10),  # value is in 10ths of a second
                        self.set_to_off,
                    )
        elif cmd == "toggle":
            self.cluster.update_attribute(self.ON_OFF, not bool(self.on_off))

    @callback
    def set_to_off(self, *_):
        """Set the state to off."""
        self._off_listener = None
        self.cluster.update_attribute(self.ON_OFF, t.Bool.false)

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.ON_OFF:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, "on_off", value
            )

    async def async_update(self):
        """Initialize channel."""
        if self.cluster.is_client:
            return
        from_cache = not self._ch_pool.is_mains_powered
        self.debug("attempting to update onoff state - from cache: %s", from_cache)
        await self.get_attribute_value(self.ON_OFF, from_cache=from_cache)
        await super().async_update()


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.OnOffConfiguration.cluster_id)
class OnOffConfiguration(ZigbeeChannel):
    """OnOff Configuration channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Ota.cluster_id)
@registries.CLIENT_CHANNELS_REGISTRY.register(general.Ota.cluster_id)
class Ota(ClientChannel):
    """OTA Channel."""

    BIND: bool = False

    @callback
    def cluster_command(
        self, tsn: int, command_id: int, args: list[Any] | None
    ) -> None:
        """Handle OTA commands."""
        if command_id in self.cluster.server_commands:
            cmd_name = self.cluster.server_commands[command_id].name
        else:
            cmd_name = command_id

        signal_id = self._ch_pool.unique_id.split("-")[0]
        if cmd_name == "query_next_image":
            assert args
            self.async_send_signal(SIGNAL_UPDATE_DEVICE.format(signal_id), args[3])


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Partition.cluster_id)
class Partition(ZigbeeChannel):
    """Partition channel."""


@registries.CHANNEL_ONLY_CLUSTERS.register(general.PollControl.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.PollControl.cluster_id)
class PollControl(ZigbeeChannel):
    """Poll Control channel."""

    CHECKIN_INTERVAL = 55 * 60 * 4  # 55min
    CHECKIN_FAST_POLL_TIMEOUT = 2 * 4  # 2s
    LONG_POLL = 6 * 4  # 6s
    _IGNORED_MANUFACTURER_ID = {
        4476,
    }  # IKEA

    async def async_configure_channel_specific(self) -> None:
        """Configure channel: set check-in interval."""
        try:
            res = await self.cluster.write_attributes(
                {"checkin_interval": self.CHECKIN_INTERVAL}
            )
            self.debug("%ss check-in interval set: %s", self.CHECKIN_INTERVAL / 4, res)
        except (asyncio.TimeoutError, zigpy.exceptions.ZigbeeException) as ex:
            self.debug("Couldn't set check-in interval: %s", ex)

    @callback
    def cluster_command(
        self, tsn: int, command_id: int, args: list[Any] | None
    ) -> None:
        """Handle commands received to this cluster."""
        if command_id in self.cluster.client_commands:
            cmd_name = self.cluster.client_commands[command_id].name
        else:
            cmd_name = command_id

        self.debug("Received %s tsn command '%s': %s", tsn, cmd_name, args)
        self.zha_send_event(cmd_name, args)
        if cmd_name == "checkin":
            self.cluster.create_catching_task(self.check_in_response(tsn))

    async def check_in_response(self, tsn: int) -> None:
        """Respond to checkin command."""
        await self.checkin_response(True, self.CHECKIN_FAST_POLL_TIMEOUT, tsn=tsn)
        if self._ch_pool.manufacturer_code not in self._IGNORED_MANUFACTURER_ID:
            await self.set_long_poll_interval(self.LONG_POLL)
        await self.fast_poll_stop()

    @callback
    def skip_manufacturer_id(self, manufacturer_code: int) -> None:
        """Block a specific manufacturer id from changing default polling."""
        self._IGNORED_MANUFACTURER_ID.add(manufacturer_code)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.PowerConfiguration.cluster_id)
class PowerConfigurationChannel(ZigbeeChannel):
    """Channel for the zigbee power configuration cluster."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="battery_voltage", config=REPORT_CONFIG_BATTERY_SAVE),
        AttrReportConfig(
            attr="battery_percentage_remaining", config=REPORT_CONFIG_BATTERY_SAVE
        ),
    )

    def async_initialize_channel_specific(self, from_cache: bool) -> Coroutine:
        """Initialize channel specific attrs."""
        attributes = [
            "battery_size",
            "battery_quantity",
        ]
        return self.get_attributes(
            attributes, from_cache=from_cache, only_cache=from_cache
        )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.PowerProfile.cluster_id)
class PowerProfile(ZigbeeChannel):
    """Power Profile channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.RSSILocation.cluster_id)
class RSSILocation(ZigbeeChannel):
    """RSSI Location channel."""


@registries.CLIENT_CHANNELS_REGISTRY.register(general.Scenes.cluster_id)
class ScenesClientChannel(ClientChannel):
    """Scenes channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Scenes.cluster_id)
class Scenes(ZigbeeChannel):
    """Scenes channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Time.cluster_id)
class Time(ZigbeeChannel):
    """Time channel."""
