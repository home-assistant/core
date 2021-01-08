"""
Channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import asyncio
from concurrent.futures import TimeoutError as Timeout
from enum import Enum
from functools import wraps
import logging
from random import uniform

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from ..helpers import (
    configure_reporting,
    construct_unique_id,
    safe_read,
    get_attr_id_by_name,
    bind_cluster,
    LogMixin,
)
from ..const import (
    REPORT_CONFIG_DEFAULT,
    SIGNAL_ATTR_UPDATED,
    ATTRIBUTE_CHANNEL,
    EVENT_RELAY_CHANNEL,
    ZDO_CHANNEL,
)
from ..registries import CLUSTER_REPORT_CONFIGS

_LOGGER = logging.getLogger(__name__)


def parse_and_log_command(channel, tsn, command_id, args):
    """Parse and log a zigbee cluster command."""
    cmd = channel.cluster.server_commands.get(command_id, [command_id])[0]
    channel.debug(
        "received '%s' command with %s args on cluster_id '%s' tsn '%s'",
        cmd,
        args,
        channel.cluster.cluster_id,
        tsn,
    )
    return cmd


def decorate_command(channel, command):
    """Wrap a cluster command to make it safe."""

    @wraps(command)
    async def wrapper(*args, **kwds):
        from zigpy.exceptions import DeliveryError

        try:
            result = await command(*args, **kwds)
            channel.debug(
                "executed command: %s %s %s %s",
                command.__name__,
                "{}: {}".format("with args", args),
                "{}: {}".format("with kwargs", kwds),
                "{}: {}".format("and result", result),
            )
            return result

        except (DeliveryError, Timeout) as ex:
            channel.debug("command failed: %s exception: %s", command.__name__, str(ex))
            return ex

    return wrapper


class ChannelStatus(Enum):
    """Status of a channel."""

    CREATED = 1
    CONFIGURED = 2
    INITIALIZED = 3


class ZigbeeChannel(LogMixin):
    """Base channel for a Zigbee cluster."""

    CHANNEL_NAME = None

    def __init__(self, cluster, device):
        """Initialize ZigbeeChannel."""
        self._channel_name = cluster.ep_attribute
        if self.CHANNEL_NAME:
            self._channel_name = self.CHANNEL_NAME
        self._generic_id = "channel_0x{:04x}".format(cluster.cluster_id)
        self._cluster = cluster
        self._zha_device = device
        self._unique_id = construct_unique_id(cluster)
        self._report_config = CLUSTER_REPORT_CONFIGS.get(
            self._cluster.cluster_id, [{"attr": 0, "config": REPORT_CONFIG_DEFAULT}]
        )
        self._status = ChannelStatus.CREATED
        self._cluster.add_listener(self)

    @property
    def generic_id(self):
        """Return the generic id for this channel."""
        return self._generic_id

    @property
    def unique_id(self):
        """Return the unique id for this channel."""
        return self._unique_id

    @property
    def cluster(self):
        """Return the zigpy cluster for this channel."""
        return self._cluster

    @property
    def device(self):
        """Return the device this channel is linked to."""
        return self._zha_device

    @property
    def name(self) -> str:
        """Return friendly name."""
        return self._channel_name

    @property
    def status(self):
        """Return the status of the channel."""
        return self._status

    def set_report_config(self, report_config):
        """Set the reporting configuration."""
        self._report_config = report_config

    async def async_configure(self):
        """Set cluster binding and attribute reporting."""
        manufacturer = None
        manufacturer_code = self._zha_device.manufacturer_code
        # Xiaomi devices don't need this and it disrupts pairing
        if self._zha_device.manufacturer != "LUMI":
            if self.cluster.cluster_id >= 0xFC00 and manufacturer_code:
                manufacturer = manufacturer_code
            await bind_cluster(self._unique_id, self.cluster)
            if not self.cluster.bind_only:
                for report_config in self._report_config:
                    attr = report_config.get("attr")
                    min_report_interval, max_report_interval, change = report_config.get(
                        "config"
                    )
                    await configure_reporting(
                        self._unique_id,
                        self.cluster,
                        attr,
                        min_report=min_report_interval,
                        max_report=max_report_interval,
                        reportable_change=change,
                        manufacturer=manufacturer,
                    )
                    await asyncio.sleep(uniform(0.1, 0.5))

        self.debug("finished channel configuration")
        self._status = ChannelStatus.CONFIGURED

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        self.debug("initializing channel: from_cache: %s", from_cache)
        self._status = ChannelStatus.INITIALIZED

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
            "zha_event",
            {
                "unique_id": self._unique_id,
                "device_ieee": str(self._zha_device.ieee),
                "command": command,
                "args": args,
            },
        )

    async def async_update(self):
        """Retrieve latest state from cluster."""
        pass

    async def get_attribute_value(self, attribute, from_cache=True):
        """Get the value for an attribute."""
        manufacturer = None
        manufacturer_code = self._zha_device.manufacturer_code
        if self.cluster.cluster_id >= 0xFC00 and manufacturer_code:
            manufacturer = manufacturer_code
        result = await safe_read(
            self._cluster,
            [attribute],
            allow_cache=from_cache,
            only_cache=from_cache,
            manufacturer=manufacturer,
        )
        return result.get(attribute)

    def log(self, level, msg, *args):
        """Log a message."""
        msg = "[%s]: " + msg
        args = (self.unique_id,) + args
        _LOGGER.log(level, msg, *args)

    def __getattr__(self, name):
        """Get attribute or a decorated cluster command."""
        if hasattr(self._cluster, name) and callable(getattr(self._cluster, name)):
            command = getattr(self._cluster, name)
            command.__name__ = name
            return decorate_command(self, command)
        return self.__getattribute__(name)


class AttributeListeningChannel(ZigbeeChannel):
    """Channel for attribute reports from the cluster."""

    CHANNEL_NAME = ATTRIBUTE_CHANNEL

    def __init__(self, cluster, device):
        """Initialize AttributeListeningChannel."""
        super().__init__(cluster, device)
        attr = self._report_config[0].get("attr")
        if isinstance(attr, str):
            self.value_attribute = get_attr_id_by_name(self.cluster, attr)
        else:
            self.value_attribute = attr

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.value_attribute:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value,
            )

    async def async_initialize(self, from_cache):
        """Initialize listener."""
        await self.get_attribute_value(
            self._report_config[0].get("attr"), from_cache=from_cache
        )
        await super().async_initialize(from_cache)


class ZDOChannel(LogMixin):
    """Channel for ZDO events."""

    def __init__(self, cluster, device):
        """Initialize ZDOChannel."""
        self.name = ZDO_CHANNEL
        self._cluster = cluster
        self._zha_device = device
        self._status = ChannelStatus.CREATED
        self._unique_id = "{}_ZDO".format(device.name)
        self._cluster.add_listener(self)

    @property
    def unique_id(self):
        """Return the unique id for this channel."""
        return self._unique_id

    @property
    def cluster(self):
        """Return the aigpy cluster for this channel."""
        return self._cluster

    @property
    def status(self):
        """Return the status of the channel."""
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
        """Initialize channel."""
        entry = self._zha_device.gateway.zha_storage.async_get_or_create(
            self._zha_device
        )
        self.debug("entry loaded from storage: %s", entry)
        self._status = ChannelStatus.INITIALIZED

    async def async_configure(self):
        """Configure channel."""
        self._status = ChannelStatus.CONFIGURED

    def log(self, level, msg, *args):
        """Log a message."""
        msg = "[%s:ZDO](%s): " + msg
        args = (self._zha_device.nwk, self._zha_device.model) + args
        _LOGGER.log(level, msg, *args)


class EventRelayChannel(ZigbeeChannel):
    """Event relay that can be attached to zigbee clusters."""

    CHANNEL_NAME = EVENT_RELAY_CHANNEL

    @callback
    def attribute_updated(self, attrid, value):
        """Handle an attribute updated on this cluster."""
        self.zha_send_event(
            self._cluster,
            SIGNAL_ATTR_UPDATED,
            {
                "attribute_id": attrid,
                "attribute_name": self._cluster.attributes.get(attrid, ["Unknown"])[0],
                "value": value,
            },
        )

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle a cluster command received on this cluster."""
        if (
            self._cluster.server_commands is not None
            and self._cluster.server_commands.get(command_id) is not None
        ):
            self.zha_send_event(
                self._cluster, self._cluster.server_commands.get(command_id)[0], args
            )
