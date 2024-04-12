"""General cluster handlers module for Zigbee Home Automation."""

from __future__ import annotations

from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from zhaquirks.quirk_ids import TUYA_PLUG_ONOFF
import zigpy.exceptions
import zigpy.types as t
import zigpy.zcl
from zigpy.zcl.clusters.general import (
    Alarms,
    AnalogInput,
    AnalogOutput,
    AnalogValue,
    ApplianceControl,
    Basic,
    BinaryInput,
    BinaryOutput,
    BinaryValue,
    Commissioning,
    DeviceTemperature,
    GreenPowerProxy,
    Groups,
    Identify,
    LevelControl,
    MultistateInput,
    MultistateOutput,
    MultistateValue,
    OnOff,
    OnOffConfiguration,
    Ota,
    Partition,
    PollControl,
    PowerConfiguration,
    PowerProfile,
    RSSILocation,
    Scenes,
    Time,
)
from zigpy.zcl.foundation import Status

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
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
from . import (
    AttrReportConfig,
    ClientClusterHandler,
    ClusterHandler,
    parse_and_log_command,
)
from .helpers import is_hue_motion_sensor

if TYPE_CHECKING:
    from ..endpoint import Endpoint


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Alarms.cluster_id)
class AlarmsClusterHandler(ClusterHandler):
    """Alarms cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogInput.cluster_id)
class AnalogInputClusterHandler(ClusterHandler):
    """Analog Input cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=AnalogInput.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.BINDABLE_CLUSTERS.register(AnalogOutput.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogOutput.cluster_id)
class AnalogOutputClusterHandler(ClusterHandler):
    """Analog Output cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=AnalogOutput.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )
    ZCL_INIT_ATTRS = {
        AnalogOutput.AttributeDefs.min_present_value.name: True,
        AnalogOutput.AttributeDefs.max_present_value.name: True,
        AnalogOutput.AttributeDefs.resolution.name: True,
        AnalogOutput.AttributeDefs.relinquish_default.name: True,
        AnalogOutput.AttributeDefs.description.name: True,
        AnalogOutput.AttributeDefs.engineering_units.name: True,
        AnalogOutput.AttributeDefs.application_type.name: True,
    }

    @property
    def present_value(self) -> float | None:
        """Return cached value of present_value."""
        return self.cluster.get(AnalogOutput.AttributeDefs.present_value.name)

    @property
    def min_present_value(self) -> float | None:
        """Return cached value of min_present_value."""
        return self.cluster.get(AnalogOutput.AttributeDefs.min_present_value.name)

    @property
    def max_present_value(self) -> float | None:
        """Return cached value of max_present_value."""
        return self.cluster.get(AnalogOutput.AttributeDefs.max_present_value.name)

    @property
    def resolution(self) -> float | None:
        """Return cached value of resolution."""
        return self.cluster.get(AnalogOutput.AttributeDefs.resolution.name)

    @property
    def relinquish_default(self) -> float | None:
        """Return cached value of relinquish_default."""
        return self.cluster.get(AnalogOutput.AttributeDefs.relinquish_default.name)

    @property
    def description(self) -> str | None:
        """Return cached value of description."""
        return self.cluster.get(AnalogOutput.AttributeDefs.description.name)

    @property
    def engineering_units(self) -> int | None:
        """Return cached value of engineering_units."""
        return self.cluster.get(AnalogOutput.AttributeDefs.engineering_units.name)

    @property
    def application_type(self) -> int | None:
        """Return cached value of application_type."""
        return self.cluster.get(AnalogOutput.AttributeDefs.application_type.name)

    async def async_set_present_value(self, value: float) -> None:
        """Update present_value."""
        await self.write_attributes_safe(
            {AnalogOutput.AttributeDefs.present_value.name: value}
        )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogValue.cluster_id)
class AnalogValueClusterHandler(ClusterHandler):
    """Analog Value cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=AnalogValue.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(ApplianceControl.cluster_id)
class ApplianceControlClusterHandler(ClusterHandler):
    """Appliance Control cluster handler."""


@registries.CLUSTER_HANDLER_ONLY_CLUSTERS.register(Basic.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Basic.cluster_id)
class BasicClusterHandler(ClusterHandler):
    """Cluster handler to interact with the basic cluster."""

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

    def __init__(self, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> None:
        """Initialize Basic cluster handler."""
        super().__init__(cluster, endpoint)
        if is_hue_motion_sensor(self) and self.cluster.endpoint.endpoint_id == 2:
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["trigger_indicator"] = True
        elif (
            self.cluster.endpoint.manufacturer == "TexasInstruments"
            and self.cluster.endpoint.model == "ti.router"
        ):
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["transmit_power"] = True
        elif self.cluster.endpoint.model == "lumi.curtain.agl001":
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["power_source"] = True


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryInput.cluster_id)
class BinaryInputClusterHandler(ClusterHandler):
    """Binary Input cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=BinaryInput.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryOutput.cluster_id)
class BinaryOutputClusterHandler(ClusterHandler):
    """Binary Output cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=BinaryOutput.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryValue.cluster_id)
class BinaryValueClusterHandler(ClusterHandler):
    """Binary Value cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=BinaryValue.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Commissioning.cluster_id)
class CommissioningClusterHandler(ClusterHandler):
    """Commissioning cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(DeviceTemperature.cluster_id)
class DeviceTemperatureClusterHandler(ClusterHandler):
    """Device Temperature cluster handler."""

    REPORT_CONFIG = (
        {
            "attr": DeviceTemperature.AttributeDefs.current_temperature.name,
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        },
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(GreenPowerProxy.cluster_id)
class GreenPowerProxyClusterHandler(ClusterHandler):
    """Green Power Proxy cluster handler."""

    BIND: bool = False


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Groups.cluster_id)
class GroupsClusterHandler(ClusterHandler):
    """Groups cluster handler."""

    BIND: bool = False


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Identify.cluster_id)
class IdentifyClusterHandler(ClusterHandler):
    """Identify cluster handler."""

    BIND: bool = False

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(self, tsn, command_id, args)

        if cmd == Identify.ServerCommandDefs.trigger_effect.name:
            self.async_send_signal(f"{self.unique_id}_{cmd}", args[0])


@registries.CLIENT_CLUSTER_HANDLER_REGISTRY.register(LevelControl.cluster_id)
class LevelControlClientClusterHandler(ClientClusterHandler):
    """LevelControl client cluster."""


@registries.BINDABLE_CLUSTERS.register(LevelControl.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(LevelControl.cluster_id)
class LevelControlClusterHandler(ClusterHandler):
    """Cluster handler for the LevelControl Zigbee cluster."""

    CURRENT_LEVEL = 0
    REPORT_CONFIG = (
        AttrReportConfig(
            attr=LevelControl.AttributeDefs.current_level.name,
            config=REPORT_CONFIG_ASAP,
        ),
    )
    ZCL_INIT_ATTRS = {
        LevelControl.AttributeDefs.on_off_transition_time.name: True,
        LevelControl.AttributeDefs.on_level.name: True,
        LevelControl.AttributeDefs.on_transition_time.name: True,
        LevelControl.AttributeDefs.off_transition_time.name: True,
        LevelControl.AttributeDefs.default_move_rate.name: True,
        LevelControl.AttributeDefs.start_up_current_level.name: True,
    }

    @property
    def current_level(self) -> int | None:
        """Return cached value of the current_level attribute."""
        return self.cluster.get(LevelControl.AttributeDefs.current_level.name)

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(self, tsn, command_id, args)

        if cmd in (
            LevelControl.ServerCommandDefs.move_to_level.name,
            LevelControl.ServerCommandDefs.move_to_level_with_on_off.name,
        ):
            self.dispatch_level_change(SIGNAL_SET_LEVEL, args[0])
        elif cmd in (
            LevelControl.ServerCommandDefs.move.name,
            LevelControl.ServerCommandDefs.move_with_on_off.name,
        ):
            # We should dim slowly -- for now, just step once
            rate = args[1]
            if args[0] == 0xFF:
                rate = 10  # Should read default move rate
            self.dispatch_level_change(SIGNAL_MOVE_LEVEL, -rate if args[0] else rate)
        elif cmd in (
            LevelControl.ServerCommandDefs.step.name,
            LevelControl.ServerCommandDefs.step_with_on_off.name,
        ):
            # Step (technically may change on/off)
            self.dispatch_level_change(
                SIGNAL_MOVE_LEVEL, -args[1] if args[0] else args[1]
            )

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
        """Handle attribute updates on this cluster."""
        self.debug("received attribute: %s update with value: %s", attrid, value)
        if attrid == self.CURRENT_LEVEL:
            self.dispatch_level_change(SIGNAL_SET_LEVEL, value)

    def dispatch_level_change(self, command, level):
        """Dispatch level change."""
        self.async_send_signal(f"{self.unique_id}_{command}", level)


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateInput.cluster_id)
class MultistateInputClusterHandler(ClusterHandler):
    """Multistate Input cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=MultistateInput.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateOutput.cluster_id)
class MultistateOutputClusterHandler(ClusterHandler):
    """Multistate Output cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=MultistateOutput.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateValue.cluster_id)
class MultistateValueClusterHandler(ClusterHandler):
    """Multistate Value cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=MultistateValue.AttributeDefs.present_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.CLIENT_CLUSTER_HANDLER_REGISTRY.register(OnOff.cluster_id)
class OnOffClientClusterHandler(ClientClusterHandler):
    """OnOff client cluster handler."""


@registries.BINDABLE_CLUSTERS.register(OnOff.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(OnOff.cluster_id)
class OnOffClusterHandler(ClusterHandler):
    """Cluster handler for the OnOff Zigbee cluster."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=OnOff.AttributeDefs.on_off.name, config=REPORT_CONFIG_IMMEDIATE
        ),
    )
    ZCL_INIT_ATTRS = {
        OnOff.AttributeDefs.start_up_on_off.name: True,
    }

    def __init__(self, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> None:
        """Initialize OnOffClusterHandler."""
        super().__init__(cluster, endpoint)
        self._off_listener = None

        if endpoint.device.quirk_id == TUYA_PLUG_ONOFF:
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["backlight_mode"] = True
            self.ZCL_INIT_ATTRS["power_on_state"] = True
            self.ZCL_INIT_ATTRS["child_lock"] = True

    @classmethod
    def matches(cls, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> bool:
        """Filter the cluster match for specific devices."""
        return not (
            cluster.endpoint.device.manufacturer == "Konke"
            and cluster.endpoint.device.model
            in ("3AFE280100510001", "3AFE170100510001")
        )

    @property
    def on_off(self) -> bool | None:
        """Return cached value of on/off attribute."""
        return self.cluster.get(OnOff.AttributeDefs.on_off.name)

    async def turn_on(self) -> None:
        """Turn the on off cluster on."""
        result = await self.on()
        if result[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to turn on: {result[1]}")
        self.cluster.update_attribute(OnOff.AttributeDefs.on_off.id, t.Bool.true)

    async def turn_off(self) -> None:
        """Turn the on off cluster off."""
        result = await self.off()
        if result[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to turn off: {result[1]}")
        self.cluster.update_attribute(OnOff.AttributeDefs.on_off.id, t.Bool.false)

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(self, tsn, command_id, args)

        if cmd in (
            OnOff.ServerCommandDefs.off.name,
            OnOff.ServerCommandDefs.off_with_effect.name,
        ):
            self.cluster.update_attribute(OnOff.AttributeDefs.on_off.id, t.Bool.false)
        elif cmd in (
            OnOff.ServerCommandDefs.on.name,
            OnOff.ServerCommandDefs.on_with_recall_global_scene.name,
        ):
            self.cluster.update_attribute(OnOff.AttributeDefs.on_off.id, t.Bool.true)
        elif cmd == OnOff.ServerCommandDefs.on_with_timed_off.name:
            should_accept = args[0]
            on_time = args[1]
            # 0 is always accept 1 is only accept when already on
            if should_accept == 0 or (should_accept == 1 and bool(self.on_off)):
                if self._off_listener is not None:
                    self._off_listener()
                    self._off_listener = None
                self.cluster.update_attribute(
                    OnOff.AttributeDefs.on_off.id, t.Bool.true
                )
                if on_time > 0:
                    self._off_listener = async_call_later(
                        self._endpoint.device.hass,
                        (on_time / 10),  # value is in 10ths of a second
                        self.set_to_off,
                    )
        elif cmd == "toggle":
            self.cluster.update_attribute(
                OnOff.AttributeDefs.on_off.id, not bool(self.on_off)
            )

    @callback
    def set_to_off(self, *_):
        """Set the state to off."""
        self._off_listener = None
        self.cluster.update_attribute(OnOff.AttributeDefs.on_off.id, t.Bool.false)

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
        """Handle attribute updates on this cluster."""
        if attrid == OnOff.AttributeDefs.on_off.id:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                attrid,
                OnOff.AttributeDefs.on_off.name,
                value,
            )

    async def async_update(self):
        """Initialize cluster handler."""
        if self.cluster.is_client:
            return
        from_cache = not self._endpoint.device.is_mains_powered
        self.debug("attempting to update onoff state - from cache: %s", from_cache)
        await self.get_attribute_value(
            OnOff.AttributeDefs.on_off.id, from_cache=from_cache
        )
        await super().async_update()


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(OnOffConfiguration.cluster_id)
class OnOffConfigurationClusterHandler(ClusterHandler):
    """OnOff Configuration cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Ota.cluster_id)
class OtaClusterHandler(ClusterHandler):
    """OTA cluster handler."""

    BIND: bool = False

    # Some devices have this cluster in the wrong collection (e.g. Third Reality)
    ZCL_INIT_ATTRS = {
        Ota.AttributeDefs.current_file_version.name: True,
    }

    @property
    def current_file_version(self) -> int | None:
        """Return cached value of current_file_version attribute."""
        return self.cluster.get(Ota.AttributeDefs.current_file_version.name)


@registries.CLIENT_CLUSTER_HANDLER_REGISTRY.register(Ota.cluster_id)
class OtaClientClusterHandler(ClientClusterHandler):
    """OTA client cluster handler."""

    BIND: bool = False

    ZCL_INIT_ATTRS = {
        Ota.AttributeDefs.current_file_version.name: True,
    }

    @callback
    def attribute_updated(self, attrid: int, value: Any, timestamp: Any) -> None:
        """Handle an attribute updated on this cluster."""
        # We intentionally avoid the `ClientClusterHandler` attribute update handler:
        # it emits a logbook event on every update, which pollutes the logbook
        ClusterHandler.attribute_updated(self, attrid, value, timestamp)

    @property
    def current_file_version(self) -> int | None:
        """Return cached value of current_file_version attribute."""
        return self.cluster.get(Ota.AttributeDefs.current_file_version.name)

    @callback
    def cluster_command(
        self, tsn: int, command_id: int, args: list[Any] | None
    ) -> None:
        """Handle OTA commands."""
        if command_id not in self.cluster.server_commands:
            return

        signal_id = self._endpoint.unique_id.split("-")[0]
        cmd_name = self.cluster.server_commands[command_id].name

        if cmd_name == Ota.ServerCommandDefs.query_next_image.name:
            assert args

            current_file_version = args[3]
            self.cluster.update_attribute(
                Ota.AttributeDefs.current_file_version.id, current_file_version
            )
            self.async_send_signal(
                SIGNAL_UPDATE_DEVICE.format(signal_id), current_file_version
            )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Partition.cluster_id)
class PartitionClusterHandler(ClusterHandler):
    """Partition cluster handler."""


@registries.CLUSTER_HANDLER_ONLY_CLUSTERS.register(PollControl.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(PollControl.cluster_id)
class PollControlClusterHandler(ClusterHandler):
    """Poll Control cluster handler."""

    CHECKIN_INTERVAL = 55 * 60 * 4  # 55min
    CHECKIN_FAST_POLL_TIMEOUT = 2 * 4  # 2s
    LONG_POLL = 6 * 4  # 6s
    _IGNORED_MANUFACTURER_ID = {
        4476,
    }  # IKEA

    async def async_configure_cluster_handler_specific(self) -> None:
        """Configure cluster handler: set check-in interval."""
        await self.write_attributes_safe(
            {PollControl.AttributeDefs.checkin_interval.name: self.CHECKIN_INTERVAL}
        )

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
        if cmd_name == PollControl.ClientCommandDefs.checkin.name:
            self.cluster.create_catching_task(self.check_in_response(tsn))

    async def check_in_response(self, tsn: int) -> None:
        """Respond to checkin command."""
        await self.checkin_response(True, self.CHECKIN_FAST_POLL_TIMEOUT, tsn=tsn)
        if self._endpoint.device.manufacturer_code not in self._IGNORED_MANUFACTURER_ID:
            await self.set_long_poll_interval(self.LONG_POLL)
        await self.fast_poll_stop()

    @callback
    def skip_manufacturer_id(self, manufacturer_code: int) -> None:
        """Block a specific manufacturer id from changing default polling."""
        self._IGNORED_MANUFACTURER_ID.add(manufacturer_code)


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(PowerConfiguration.cluster_id)
class PowerConfigurationClusterHandler(ClusterHandler):
    """Cluster handler for the zigbee power configuration cluster."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=PowerConfiguration.AttributeDefs.battery_voltage.name,
            config=REPORT_CONFIG_BATTERY_SAVE,
        ),
        AttrReportConfig(
            attr=PowerConfiguration.AttributeDefs.battery_percentage_remaining.name,
            config=REPORT_CONFIG_BATTERY_SAVE,
        ),
    )

    def async_initialize_cluster_handler_specific(self, from_cache: bool) -> Coroutine:
        """Initialize cluster handler specific attrs."""
        attributes = [
            PowerConfiguration.AttributeDefs.battery_size.name,
            PowerConfiguration.AttributeDefs.battery_quantity.name,
        ]
        return self.get_attributes(
            attributes, from_cache=from_cache, only_cache=from_cache
        )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(PowerProfile.cluster_id)
class PowerProfileClusterHandler(ClusterHandler):
    """Power Profile cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(RSSILocation.cluster_id)
class RSSILocationClusterHandler(ClusterHandler):
    """RSSI Location cluster handler."""


@registries.CLIENT_CLUSTER_HANDLER_REGISTRY.register(Scenes.cluster_id)
class ScenesClientClusterHandler(ClientClusterHandler):
    """Scenes cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Scenes.cluster_id)
class ScenesClusterHandler(ClusterHandler):
    """Scenes cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Time.cluster_id)
class TimeClusterHandler(ClusterHandler):
    """Time cluster handler."""
