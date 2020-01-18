"""
General channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import logging

import zigpy.zcl.clusters.general as general

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from . import AttributeListeningChannel, ZigbeeChannel, parse_and_log_command
from .. import registries
from ..const import (
    REPORT_CONFIG_ASAP,
    REPORT_CONFIG_BATTERY_SAVE,
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_MOVE_LEVEL,
    SIGNAL_SET_LEVEL,
    SIGNAL_STATE_ATTR,
)
from ..helpers import get_attr_id_by_name

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Alarms.cluster_id)
class Alarms(ZigbeeChannel):
    """Alarms channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.AnalogInput.cluster_id)
class AnalogInput(AttributeListeningChannel):
    """Analog Input channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.AnalogOutput.cluster_id)
class AnalogOutput(AttributeListeningChannel):
    """Analog Output channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.AnalogValue.cluster_id)
class AnalogValue(AttributeListeningChannel):
    """Analog Value channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.ApplianceControl.cluster_id)
class ApplianceContorl(ZigbeeChannel):
    """Appliance Control channel."""

    pass


@registries.CHANNEL_ONLY_CLUSTERS.register(general.Basic.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Basic.cluster_id)
class BasicChannel(ZigbeeChannel):
    """Channel to interact with the basic cluster."""

    UNKNOWN = 0
    BATTERY = 3

    POWER_SOURCES = {
        UNKNOWN: "Unknown",
        1: "Mains (single phase)",
        2: "Mains (3 phase)",
        BATTERY: "Battery",
        4: "DC source",
        5: "Emergency mains constantly powered",
        6: "Emergency mains and transfer switch",
    }

    def __init__(self, cluster, device):
        """Initialize BasicChannel."""
        super().__init__(cluster, device)
        self._power_source = None

    async def async_configure(self):
        """Configure this channel."""
        await super().async_configure()
        await self.async_initialize(False)

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        self._power_source = await self.get_attribute_value(
            "power_source", from_cache=from_cache
        )
        await super().async_initialize(from_cache)

    def get_power_source(self):
        """Get the power source."""
        return self._power_source


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.BinaryInput.cluster_id)
class BinaryInput(AttributeListeningChannel):
    """Binary Input channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.BinaryOutput.cluster_id)
class BinaryOutput(AttributeListeningChannel):
    """Binary Output channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.BinaryValue.cluster_id)
class BinaryValue(AttributeListeningChannel):
    """Binary Value channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Commissioning.cluster_id)
class Commissioning(ZigbeeChannel):
    """Commissioning channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.DeviceTemperature.cluster_id)
class DeviceTemperature(ZigbeeChannel):
    """Device Temperature channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.GreenPowerProxy.cluster_id)
class GreenPowerProxy(ZigbeeChannel):
    """Green Power Proxy channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Groups.cluster_id)
class Groups(ZigbeeChannel):
    """Groups channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Identify.cluster_id)
class Identify(ZigbeeChannel):
    """Identify channel."""

    pass


@registries.BINDABLE_CLUSTERS.register(general.LevelControl.cluster_id)
@registries.EVENT_RELAY_CLUSTERS.register(general.LevelControl.cluster_id)
@registries.LIGHT_CLUSTERS.register(general.LevelControl.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.LevelControl.cluster_id)
class LevelControlChannel(ZigbeeChannel):
    """Channel for the LevelControl Zigbee cluster."""

    CURRENT_LEVEL = 0
    REPORT_CONFIG = ({"attr": "current_level", "config": REPORT_CONFIG_ASAP},)

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
        async_dispatcher_send(
            self._zha_device.hass, f"{self.unique_id}_{command}", level
        )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(self.CURRENT_LEVEL, from_cache=from_cache)
        await super().async_initialize(from_cache)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.MultistateInput.cluster_id)
class MultistateInput(AttributeListeningChannel):
    """Multistate Input channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.MultistateOutput.cluster_id)
class MultistateOutput(AttributeListeningChannel):
    """Multistate Output channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.MultistateValue.cluster_id)
class MultistateValue(AttributeListeningChannel):
    """Multistate Value channel."""

    REPORT_CONFIG = [{"attr": "present_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.BINARY_SENSOR_CLUSTERS.register(general.OnOff.cluster_id)
@registries.BINDABLE_CLUSTERS.register(general.OnOff.cluster_id)
@registries.EVENT_RELAY_CLUSTERS.register(general.OnOff.cluster_id)
@registries.LIGHT_CLUSTERS.register(general.OnOff.cluster_id)
@registries.SWITCH_CLUSTERS.register(general.OnOff.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.OnOff.cluster_id)
class OnOffChannel(ZigbeeChannel):
    """Channel for the OnOff Zigbee cluster."""

    ON_OFF = 0
    REPORT_CONFIG = ({"attr": "on_off", "config": REPORT_CONFIG_IMMEDIATE},)

    def __init__(self, cluster, device):
        """Initialize OnOffChannel."""
        super().__init__(cluster, device)
        self._state = None
        self._off_listener = None

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(self, tsn, command_id, args)

        if cmd in ("off", "off_with_effect"):
            self.attribute_updated(self.ON_OFF, False)
        elif cmd in ("on", "on_with_recall_global_scene"):
            self.attribute_updated(self.ON_OFF, True)
        elif cmd == "on_with_timed_off":
            should_accept = args[0]
            on_time = args[1]
            # 0 is always accept 1 is only accept when already on
            if should_accept == 0 or (should_accept == 1 and self._state):
                if self._off_listener is not None:
                    self._off_listener()
                    self._off_listener = None
                self.attribute_updated(self.ON_OFF, True)
                if on_time > 0:
                    self._off_listener = async_call_later(
                        self.device.hass,
                        (on_time / 10),  # value is in 10ths of a second
                        self.set_to_off,
                    )
        elif cmd == "toggle":
            self.attribute_updated(self.ON_OFF, not bool(self._state))

    @callback
    def set_to_off(self, *_):
        """Set the state to off."""
        self._off_listener = None
        self.attribute_updated(self.ON_OFF, False)

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.ON_OFF:
            async_dispatcher_send(
                self._zha_device.hass, f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", value
            )
            self._state = bool(value)

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        self._state = bool(
            await self.get_attribute_value(self.ON_OFF, from_cache=from_cache)
        )
        await super().async_initialize(from_cache)

    async def async_update(self):
        """Initialize channel."""
        from_cache = not self.device.is_mains_powered
        self.debug("attempting to update onoff state - from cache: %s", from_cache)
        self._state = bool(
            await self.get_attribute_value(self.ON_OFF, from_cache=from_cache)
        )
        await super().async_update()


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.OnOffConfiguration.cluster_id)
class OnOffConfiguration(ZigbeeChannel):
    """OnOff Configuration channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Ota.cluster_id)
class Ota(ZigbeeChannel):
    """OTA Channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Partition.cluster_id)
class Partition(ZigbeeChannel):
    """Partition channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.PollControl.cluster_id)
class PollControl(ZigbeeChannel):
    """Poll Control channel."""

    pass


@registries.DEVICE_TRACKER_CLUSTERS.register(general.PowerConfiguration.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.PowerConfiguration.cluster_id)
class PowerConfigurationChannel(ZigbeeChannel):
    """Channel for the zigbee power configuration cluster."""

    REPORT_CONFIG = (
        {"attr": "battery_voltage", "config": REPORT_CONFIG_BATTERY_SAVE},
        {"attr": "battery_percentage_remaining", "config": REPORT_CONFIG_BATTERY_SAVE},
    )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        attr = self._report_config[1].get("attr")
        if isinstance(attr, str):
            attr_id = get_attr_id_by_name(self.cluster, attr)
        else:
            attr_id = attr
        if attrid == attr_id:
            async_dispatcher_send(
                self._zha_device.hass, f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", value
            )
            return
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        async_dispatcher_send(
            self._zha_device.hass,
            f"{self.unique_id}_{SIGNAL_STATE_ATTR}",
            attr_name,
            value,
        )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.async_read_state(from_cache)
        await super().async_initialize(from_cache)

    async def async_update(self):
        """Retrieve latest state."""
        await self.async_read_state(True)

    async def async_read_state(self, from_cache):
        """Read data from the cluster."""
        await self.get_attribute_value("battery_size", from_cache=from_cache)
        await self.get_attribute_value(
            "battery_percentage_remaining", from_cache=from_cache
        )
        await self.get_attribute_value("battery_voltage", from_cache=from_cache)
        await self.get_attribute_value("battery_quantity", from_cache=from_cache)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.PowerProfile.cluster_id)
class PowerProfile(ZigbeeChannel):
    """Power Profile channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.RSSILocation.cluster_id)
class RSSILocation(ZigbeeChannel):
    """RSSI Location channel."""

    pass


@registries.OUTPUT_CHANNEL_ONLY_CLUSTERS.register(general.Scenes.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Scenes.cluster_id)
class Scenes(ZigbeeChannel):
    """Scenes channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(general.Time.cluster_id)
class Time(ZigbeeChannel):
    """Time channel."""

    pass
