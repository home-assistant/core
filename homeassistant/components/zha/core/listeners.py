"""
Cluster listeners for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import asyncio
from enum import Enum
from functools import wraps
import logging
from random import uniform

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .helpers import (
    bind_configure_reporting, construct_unique_id,
    safe_read, get_attr_id_by_name, bind_cluster)
from .const import (
    CLUSTER_REPORT_CONFIGS, REPORT_CONFIG_DEFAULT, SIGNAL_ATTR_UPDATED,
    SIGNAL_MOVE_LEVEL, SIGNAL_SET_LEVEL, SIGNAL_STATE_ATTR, LISTENER_BASIC,
    LISTENER_ATTRIBUTE, LISTENER_ON_OFF, LISTENER_COLOR, LISTENER_FAN,
    LISTENER_LEVEL, LISTENER_ZONE, LISTENER_ACTIVE_POWER, LISTENER_BATTERY,
    LISTENER_EVENT_RELAY
)

LISTENER_REGISTRY = {}

_LOGGER = logging.getLogger(__name__)


def populate_listener_registry():
    """Populate the listener registry."""
    from zigpy import zcl
    LISTENER_REGISTRY.update({
        zcl.clusters.general.Alarms.cluster_id: ClusterListener,
        zcl.clusters.general.Commissioning.cluster_id: ClusterListener,
        zcl.clusters.general.Identify.cluster_id: ClusterListener,
        zcl.clusters.general.Groups.cluster_id: ClusterListener,
        zcl.clusters.general.Scenes.cluster_id: ClusterListener,
        zcl.clusters.general.Partition.cluster_id: ClusterListener,
        zcl.clusters.general.Ota.cluster_id: ClusterListener,
        zcl.clusters.general.PowerProfile.cluster_id: ClusterListener,
        zcl.clusters.general.ApplianceControl.cluster_id: ClusterListener,
        zcl.clusters.general.PollControl.cluster_id: ClusterListener,
        zcl.clusters.general.GreenPowerProxy.cluster_id: ClusterListener,
        zcl.clusters.general.OnOffConfiguration.cluster_id: ClusterListener,
        zcl.clusters.general.OnOff.cluster_id: OnOffListener,
        zcl.clusters.general.LevelControl.cluster_id: LevelListener,
        zcl.clusters.lighting.Color.cluster_id: ColorListener,
        zcl.clusters.homeautomation.ElectricalMeasurement.cluster_id:
        ActivePowerListener,
        zcl.clusters.general.PowerConfiguration.cluster_id: BatteryListener,
        zcl.clusters.general.Basic.cluster_id: BasicListener,
        zcl.clusters.security.IasZone.cluster_id: IASZoneListener,
        zcl.clusters.hvac.Fan.cluster_id: FanListener,
    })


def parse_and_log_command(unique_id, cluster, tsn, command_id, args):
    """Parse and log a zigbee cluster command."""
    cmd = cluster.server_commands.get(command_id, [command_id])[0]
    _LOGGER.debug(
        "%s: received '%s' command with %s args on cluster_id '%s' tsn '%s'",
        unique_id,
        cmd,
        args,
        cluster.cluster_id,
        tsn
    )
    return cmd


def decorate_command(listener, command):
    """Wrap a cluster command to make it safe."""
    @wraps(command)
    async def wrapper(*args, **kwds):
        from zigpy.zcl.foundation import Status
        from zigpy.exceptions import DeliveryError
        try:
            result = await command(*args, **kwds)
            _LOGGER.debug("%s: executed command: %s %s %s %s",
                          listener.unique_id,
                          command.__name__,
                          "{}: {}".format("with args", args),
                          "{}: {}".format("with kwargs", kwds),
                          "{}: {}".format("and result", result))
            if isinstance(result, bool):
                return result
            return result[1] is Status.SUCCESS
        except DeliveryError:
            _LOGGER.debug("%s: command failed: %s", listener.unique_id,
                          command.__name__)
            return False
    return wrapper


class ListenerStatus(Enum):
    """Status of a listener."""

    CREATED = 1
    CONFIGURED = 2
    INITIALIZED = 3


class ClusterListener:
    """Listener for a Zigbee cluster."""

    def __init__(self, cluster, device):
        """Initialize ClusterListener."""
        self.name = 'cluster_{}'.format(cluster.cluster_id)
        self._cluster = cluster
        self._zha_device = device
        self._unique_id = construct_unique_id(cluster)
        self._report_config = CLUSTER_REPORT_CONFIGS.get(
            self._cluster.cluster_id,
            [{'attr': 0, 'config': REPORT_CONFIG_DEFAULT}]
        )
        self._status = ListenerStatus.CREATED
        self._cluster.add_listener(self)

    @property
    def unique_id(self):
        """Return the unique id for this listener."""
        return self._unique_id

    @property
    def cluster(self):
        """Return the zigpy cluster for this listener."""
        return self._cluster

    @property
    def device(self):
        """Return the device this listener is linked to."""
        return self._zha_device

    @property
    def status(self):
        """Return the status of the listener."""
        return self._status

    def set_report_config(self, report_config):
        """Set the reporting configuration."""
        self._report_config = report_config

    async def async_configure(self):
        """Set cluster binding and attribute reporting."""
        manufacturer = None
        manufacturer_code = self._zha_device.manufacturer_code
        if self.cluster.cluster_id >= 0xfc00 and manufacturer_code:
            manufacturer = manufacturer_code

        skip_bind = False  # bind cluster only for the 1st configured attr
        for report_config in self._report_config:
            attr = report_config.get('attr')
            min_report_interval, max_report_interval, change = \
                report_config.get('config')
            await bind_configure_reporting(
                self._unique_id, self.cluster, attr,
                min_report=min_report_interval,
                max_report=max_report_interval,
                reportable_change=change,
                skip_bind=skip_bind,
                manufacturer=manufacturer
            )
            skip_bind = True
            await asyncio.sleep(uniform(0.1, 0.5))
        _LOGGER.debug(
            "%s: finished listener configuration",
            self._unique_id
        )
        self._status = ListenerStatus.CONFIGURED

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        self._status = ListenerStatus.INITIALIZED

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        pass

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        pass

    @callback
    def zdo_command(self, *args, **kwargs):
        """Handle ZDO commands on this cluster."""
        pass

    @callback
    def zha_send_event(self, cluster, command, args):
        """Relay events to hass."""
        self._zha_device.hass.bus.async_fire(
            'zha_event',
            {
                'unique_id': self._unique_id,
                'device_ieee': str(self._zha_device.ieee),
                'command': command,
                'args': args
            }
        )

    async def async_update(self):
        """Retrieve latest state from cluster."""
        pass

    async def get_attribute_value(self, attribute, from_cache=True):
        """Get the value for an attribute."""
        result = await safe_read(
            self._cluster,
            [attribute],
            allow_cache=from_cache,
            only_cache=from_cache
        )
        return result.get(attribute)

    def __getattr__(self, name):
        """Get attribute or a decorated cluster command."""
        if hasattr(self._cluster, name) and callable(
                getattr(self._cluster, name)):
            command = getattr(self._cluster, name)
            command.__name__ = name
            return decorate_command(
                self,
                command
            )
        return self.__getattribute__(name)


class AttributeListener(ClusterListener):
    """Listener for the attribute reports cluster."""

    def __init__(self, cluster, device):
        """Initialize AttributeListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_ATTRIBUTE
        attr = self._report_config[0].get('attr')
        if isinstance(attr, str):
            self._value_attribute = get_attr_id_by_name(self.cluster, attr)
        else:
            self._value_attribute = attr

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self._value_attribute:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value
            )

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        await self.get_attribute_value(
            self._report_config[0].get('attr'), from_cache=from_cache)
        await super().async_initialize(from_cache)


class OnOffListener(ClusterListener):
    """Listener for the OnOff Zigbee cluster."""

    ON_OFF = 0

    def __init__(self, cluster, device):
        """Initialize OnOffListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_ON_OFF
        self._state = None

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(
            self.unique_id,
            self._cluster,
            tsn,
            command_id,
            args
        )

        if cmd in ('off', 'off_with_effect'):
            self.attribute_updated(self.ON_OFF, False)
        elif cmd in ('on', 'on_with_recall_global_scene', 'on_with_timed_off'):
            self.attribute_updated(self.ON_OFF, True)
        elif cmd == 'toggle':
            self.attribute_updated(self.ON_OFF, not bool(self._state))

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.ON_OFF:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value
            )
            self._state = bool(value)

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        self._state = bool(
            await self.get_attribute_value(self.ON_OFF, from_cache=from_cache))
        await super().async_initialize(from_cache)


class LevelListener(ClusterListener):
    """Listener for the LevelControl Zigbee cluster."""

    CURRENT_LEVEL = 0

    def __init__(self, cluster, device):
        """Initialize LevelListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_LEVEL

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(
            self.unique_id,
            self._cluster,
            tsn,
            command_id,
            args
        )

        if cmd in ('move_to_level', 'move_to_level_with_on_off'):
            self.dispatch_level_change(SIGNAL_SET_LEVEL, args[0])
        elif cmd in ('move', 'move_with_on_off'):
            # We should dim slowly -- for now, just step once
            rate = args[1]
            if args[0] == 0xff:
                rate = 10  # Should read default move rate
            self.dispatch_level_change(
                SIGNAL_MOVE_LEVEL, -rate if args[0] else rate)
        elif cmd in ('step', 'step_with_on_off'):
            # Step (technically may change on/off)
            self.dispatch_level_change(
                SIGNAL_MOVE_LEVEL, -args[1] if args[0] else args[1])

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        _LOGGER.debug("%s: received attribute: %s update with value: %i",
                      self.unique_id, attrid, value)
        if attrid == self.CURRENT_LEVEL:
            self.dispatch_level_change(SIGNAL_SET_LEVEL, value)

    def dispatch_level_change(self, command, level):
        """Dispatch level change."""
        async_dispatcher_send(
            self._zha_device.hass,
            "{}_{}".format(self.unique_id, command),
            level
        )

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        await self.get_attribute_value(
            self.CURRENT_LEVEL, from_cache=from_cache)
        await super().async_initialize(from_cache)


class IASZoneListener(ClusterListener):
    """Listener for the IASZone Zigbee cluster."""

    def __init__(self, cluster, device):
        """Initialize LevelListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_ZONE

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            state = args[0] & 3
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                state
            )
            _LOGGER.debug("Updated alarm state: %s", state)
        elif command_id == 1:
            _LOGGER.debug("Enroll requested")
            res = self._cluster.enroll_response(0, 0)
            self._zha_device.hass.async_create_task(res)

    async def async_configure(self):
        """Configure IAS device."""
        from zigpy.exceptions import DeliveryError
        _LOGGER.debug("%s: started IASZoneListener configuration",
                      self._unique_id)

        await bind_cluster(self.unique_id, self._cluster)
        ieee = self._cluster.endpoint.device.application.ieee

        try:
            res = await self._cluster.write_attributes({'cie_addr': ieee})
            _LOGGER.debug(
                "%s: wrote cie_addr: %s to '%s' cluster: %s",
                self.unique_id, str(ieee), self._cluster.ep_attribute,
                res[0]
            )
        except DeliveryError as ex:
            _LOGGER.debug(
                "%s: Failed to write cie_addr: %s to '%s' cluster: %s",
                self.unique_id, str(ieee), self._cluster.ep_attribute, str(ex)
            )
        _LOGGER.debug("%s: finished IASZoneListener configuration",
                      self._unique_id)

        await self.get_attribute_value('zone_type', from_cache=False)

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == 2:
            value = value & 3
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value
            )

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        await self.get_attribute_value('zone_status', from_cache=from_cache)
        await self.get_attribute_value('zone_state', from_cache=from_cache)
        await super().async_initialize(from_cache)


class ActivePowerListener(AttributeListener):
    """Listener that polls active power level."""

    def __init__(self, cluster, device):
        """Initialize ActivePowerListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_ACTIVE_POWER

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("%s async_update", self.unique_id)

        # This is a polling listener. Don't allow cache.
        result = await self.get_attribute_value(
            LISTENER_ACTIVE_POWER, from_cache=False)
        async_dispatcher_send(
            self._zha_device.hass,
            "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
            result
        )

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        await self.get_attribute_value(
            LISTENER_ACTIVE_POWER, from_cache=from_cache)
        await super().async_initialize(from_cache)


class BasicListener(ClusterListener):
    """Listener to interact with the basic cluster."""

    BATTERY = 3
    POWER_SOURCES = {
        0: 'Unknown',
        1: 'Mains (single phase)',
        2: 'Mains (3 phase)',
        BATTERY: 'Battery',
        4: 'DC source',
        5: 'Emergency mains constantly powered',
        6: 'Emergency mains and transfer switch'
    }

    def __init__(self, cluster, device):
        """Initialize BasicListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_BASIC
        self._power_source = None

    async def async_configure(self):
        """Configure this listener."""
        await super().async_configure()
        await self.async_initialize(False)

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        self._power_source = await self.get_attribute_value(
            'power_source', from_cache=from_cache)
        await super().async_initialize(from_cache)

    def get_power_source(self):
        """Get the power source."""
        return self._power_source


class BatteryListener(ClusterListener):
    """Listener that polls active power level."""

    def __init__(self, cluster, device):
        """Initialize BatteryListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_BATTERY

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        attr = self._report_config[1].get('attr')
        if isinstance(attr, str):
            attr_id = get_attr_id_by_name(self.cluster, attr)
        else:
            attr_id = attr
        if attrid == attr_id:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_STATE_ATTR),
                'battery_level',
                value
            )

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        await self.async_read_state(from_cache)
        await super().async_initialize(from_cache)

    async def async_update(self):
        """Retrieve latest state."""
        await self.async_read_state(True)

    async def async_read_state(self, from_cache):
        """Read data from the cluster."""
        await self.get_attribute_value(
            'battery_size', from_cache=from_cache)
        await self.get_attribute_value(
            'battery_percentage_remaining', from_cache=from_cache)
        await self.get_attribute_value(
            'active_power', from_cache=from_cache)


class EventRelayListener(ClusterListener):
    """Event relay that can be attached to zigbee clusters."""

    def __init__(self, cluster, device):
        """Initialize EventRelayListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_EVENT_RELAY

    @callback
    def attribute_updated(self, attrid, value):
        """Handle an attribute updated on this cluster."""
        self.zha_send_event(
            self._cluster,
            SIGNAL_ATTR_UPDATED,
            {
                'attribute_id': attrid,
                'attribute_name': self._cluster.attributes.get(
                    attrid,
                    ['Unknown'])[0],
                'value': value
            }
        )

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle a cluster command received on this cluster."""
        if self._cluster.server_commands is not None and \
                self._cluster.server_commands.get(command_id) is not None:
            self.zha_send_event(
                self._cluster,
                self._cluster.server_commands.get(command_id)[0],
                args
            )


class ColorListener(ClusterListener):
    """Color listener."""

    CAPABILITIES_COLOR_XY = 0x08
    CAPABILITIES_COLOR_TEMP = 0x10
    UNSUPPORTED_ATTRIBUTE = 0x86

    def __init__(self, cluster, device):
        """Initialize ColorListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_COLOR
        self._color_capabilities = None

    def get_color_capabilities(self):
        """Return the color capabilities."""
        return self._color_capabilities

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        capabilities = await self.get_attribute_value(
            'color_capabilities', from_cache=from_cache)

        if capabilities is None:
            # ZCL Version 4 devices don't support the color_capabilities
            # attribute. In this version XY support is mandatory, but we
            # need to probe to determine if the device supports color
            # temperature.
            capabilities = self.CAPABILITIES_COLOR_XY
            result = await self.get_attribute_value(
                'color_temperature', from_cache=from_cache)

            if result is not self.UNSUPPORTED_ATTRIBUTE:
                capabilities |= self.CAPABILITIES_COLOR_TEMP
        self._color_capabilities = capabilities
        await super().async_initialize(from_cache)


class FanListener(ClusterListener):
    """Fan listener."""

    _value_attribute = 0

    def __init__(self, cluster, device):
        """Initialize FanListener."""
        super().__init__(cluster, device)
        self.name = LISTENER_FAN

    async def async_set_speed(self, value) -> None:
        """Set the speed of the fan."""
        from zigpy.exceptions import DeliveryError
        try:
            await self.cluster.write_attributes({'fan_mode': value})
        except DeliveryError as ex:
            _LOGGER.error("%s: Could not set speed: %s", self.unique_id, ex)
            return

    async def async_update(self):
        """Retrieve latest state."""
        result = await self.get_attribute_value('fan_mode', from_cache=True)

        async_dispatcher_send(
            self._zha_device.hass,
            "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
            result
        )

    def attribute_updated(self, attrid, value):
        """Handle attribute update from fan cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        _LOGGER.debug("%s: Attribute report '%s'[%s] = %s",
                      self.unique_id, self.cluster.name, attr_name, value)
        if attrid == self._value_attribute:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value
            )

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        await self.get_attribute_value(
            self._value_attribute, from_cache=from_cache)
        await super().async_initialize(from_cache)


class ZDOListener:
    """Listener for ZDO events."""

    def __init__(self, cluster, device):
        """Initialize ZDOListener."""
        self.name = 'zdo'
        self._cluster = cluster
        self._zha_device = device
        self._status = ListenerStatus.CREATED
        self._unique_id = "{}_ZDO".format(device.name)
        self._cluster.add_listener(self)

    @property
    def unique_id(self):
        """Return the unique id for this listener."""
        return self._unique_id

    @property
    def cluster(self):
        """Return the aigpy cluster for this listener."""
        return self._cluster

    @property
    def status(self):
        """Return the status of the listener."""
        return self._status

    @callback
    def device_announce(self, zigpy_device):
        """Device announce handler."""
        pass

    @callback
    def permit_duration(self, duration):
        """Permit handler."""
        pass

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        self._status = ListenerStatus.INITIALIZED

    async def async_configure(self):
        """Configure listener."""
        self._status = ListenerStatus.CONFIGURED
