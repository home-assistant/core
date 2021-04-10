"""Base classes for channels."""
from __future__ import annotations

import asyncio
from enum import Enum
from functools import wraps
import logging
from typing import Any

import zigpy.exceptions

from homeassistant.const import ATTR_COMMAND
from homeassistant.core import callback

from .. import typing as zha_typing
from ..const import (
    ATTR_ARGS,
    ATTR_ATTRIBUTE_ID,
    ATTR_ATTRIBUTE_NAME,
    ATTR_CLUSTER_ID,
    ATTR_UNIQUE_ID,
    ATTR_VALUE,
    CHANNEL_ZDO,
    SIGNAL_ATTR_UPDATED,
)
from ..helpers import LogMixin, safe_read

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
        try:
            result = await command(*args, **kwds)
            channel.debug(
                "executed '%s' command with args: '%s' kwargs: '%s' result: %s",
                command.__name__,
                args,
                kwds,
                result,
            )
            return result

        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            channel.debug(
                "command failed: '%s' args: '%s' kwargs '%s' exception: '%s'",
                command.__name__,
                args,
                kwds,
                str(ex),
            )
            return ex

    return wrapper


class ChannelStatus(Enum):
    """Status of a channel."""

    CREATED = 1
    CONFIGURED = 2
    INITIALIZED = 3


class ZigbeeChannel(LogMixin):
    """Base channel for a Zigbee cluster."""

    REPORT_CONFIG = ()

    def __init__(
        self, cluster: zha_typing.ZigpyClusterType, ch_pool: zha_typing.ChannelPoolType
    ) -> None:
        """Initialize ZigbeeChannel."""
        self._generic_id = f"channel_0x{cluster.cluster_id:04x}"
        self._channel_name = getattr(cluster, "ep_attribute", self._generic_id)
        self._ch_pool = ch_pool
        self._cluster = cluster
        self._id = f"{ch_pool.id}:0x{cluster.cluster_id:04x}"
        unique_id = ch_pool.unique_id.replace("-", ":")
        self._unique_id = f"{unique_id}:0x{cluster.cluster_id:04x}"
        self._report_config = self.REPORT_CONFIG
        if not hasattr(self, "_value_attribute") and len(self._report_config) > 0:
            attr = self._report_config[0].get("attr")
            if isinstance(attr, str):
                self.value_attribute = self.cluster.attridx.get(attr)
            else:
                self.value_attribute = attr
        self._status = ChannelStatus.CREATED
        self._cluster.add_listener(self)

    @property
    def id(self) -> str:
        """Return channel id unique for this device only."""
        return self._id

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
    def name(self) -> str:
        """Return friendly name."""
        return self._channel_name

    @property
    def status(self):
        """Return the status of the channel."""
        return self._status

    @callback
    def async_send_signal(self, signal: str, *args: Any) -> None:
        """Send a signal through hass dispatcher."""
        self._ch_pool.async_send_signal(signal, *args)

    async def bind(self):
        """Bind a zigbee cluster.

        This also swallows ZigbeeException exceptions that are thrown when
        devices are unreachable.
        """
        try:
            res = await self.cluster.bind()
            self.debug("bound '%s' cluster: %s", self.cluster.ep_attribute, res[0])
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                "Failed to bind '%s' cluster: %s", self.cluster.ep_attribute, str(ex)
            )

    async def configure_reporting(self) -> None:
        """Configure attribute reporting for a cluster.

        This also swallows ZigbeeException exceptions that are thrown when
        devices are unreachable.
        """
        kwargs = {}
        if self.cluster.cluster_id >= 0xFC00 and self._ch_pool.manufacturer_code:
            kwargs["manufacturer"] = self._ch_pool.manufacturer_code

        for report in self._report_config:
            attr = report["attr"]
            attr_name = self.cluster.attributes.get(attr, [attr])[0]
            min_report_int, max_report_int, reportable_change = report["config"]
            try:
                res = await self.cluster.configure_reporting(
                    attr, min_report_int, max_report_int, reportable_change, **kwargs
                )
                self.debug(
                    "reporting '%s' attr on '%s' cluster: %d/%d/%d: Result: '%s'",
                    attr_name,
                    self.cluster.ep_attribute,
                    min_report_int,
                    max_report_int,
                    reportable_change,
                    res,
                )
            except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
                self.debug(
                    "failed to set reporting for '%s' attr on '%s' cluster: %s",
                    attr_name,
                    self.cluster.ep_attribute,
                    str(ex),
                )

    async def async_configure(self) -> None:
        """Set cluster binding and attribute reporting."""
        if not self._ch_pool.skip_configuration:
            await self.bind()
            if self.cluster.is_server:
                await self.configure_reporting()
            ch_specific_cfg = getattr(self, "async_configure_channel_specific", None)
            if ch_specific_cfg:
                await ch_specific_cfg()
            self.debug("finished channel configuration")
        else:
            self.debug("skipping channel configuration")
        self._status = ChannelStatus.CONFIGURED

    async def async_initialize(self, from_cache: bool) -> None:
        """Initialize channel."""
        if not from_cache and self._ch_pool.skip_configuration:
            self._status = ChannelStatus.INITIALIZED
            return

        self.debug("initializing channel: from_cache: %s", from_cache)
        attributes = [cfg["attr"] for cfg in self._report_config]
        if attributes:
            await self.get_attributes(attributes, from_cache=from_cache)

        ch_specific_init = getattr(self, "async_initialize_channel_specific", None)
        if ch_specific_init:
            await ch_specific_init(from_cache=from_cache)

        self.debug("finished channel configuration")
        self._status = ChannelStatus.INITIALIZED

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        self.async_send_signal(
            f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
            attrid,
            self.cluster.attributes.get(attrid, [attrid])[0],
            value,
        )

    @callback
    def zdo_command(self, *args, **kwargs):
        """Handle ZDO commands on this cluster."""

    @callback
    def zha_send_event(self, command: str, args: int | dict) -> None:
        """Relay events to hass."""
        self._ch_pool.zha_send_event(
            {
                ATTR_UNIQUE_ID: self.unique_id,
                ATTR_CLUSTER_ID: self.cluster.cluster_id,
                ATTR_COMMAND: command,
                ATTR_ARGS: args,
            }
        )

    async def async_update(self):
        """Retrieve latest state from cluster."""

    async def get_attribute_value(self, attribute, from_cache=True):
        """Get the value for an attribute."""
        manufacturer = None
        manufacturer_code = self._ch_pool.manufacturer_code
        if self.cluster.cluster_id >= 0xFC00 and manufacturer_code:
            manufacturer = manufacturer_code
        result = await safe_read(
            self._cluster,
            [attribute],
            allow_cache=from_cache,
            only_cache=from_cache and not self._ch_pool.is_mains_powered,
            manufacturer=manufacturer,
        )
        return result.get(attribute)

    async def get_attributes(self, attributes, from_cache=True):
        """Get the values for a list of attributes."""
        manufacturer = None
        manufacturer_code = self._ch_pool.manufacturer_code
        if self.cluster.cluster_id >= 0xFC00 and manufacturer_code:
            manufacturer = manufacturer_code
        try:
            result, _ = await self.cluster.read_attributes(
                attributes,
                allow_cache=from_cache,
                only_cache=from_cache and not self._ch_pool.is_mains_powered,
                manufacturer=manufacturer,
            )
            return result
        except (asyncio.TimeoutError, zigpy.exceptions.ZigbeeException) as ex:
            self.debug(
                "failed to get attributes '%s' on '%s' cluster: %s",
                attributes,
                self.cluster.ep_attribute,
                str(ex),
            )
            return {}

    def log(self, level, msg, *args):
        """Log a message."""
        msg = f"[%s:%s]: {msg}"
        args = (self._ch_pool.nwk, self._id) + args
        _LOGGER.log(level, msg, *args)

    def __getattr__(self, name):
        """Get attribute or a decorated cluster command."""
        if hasattr(self._cluster, name) and callable(getattr(self._cluster, name)):
            command = getattr(self._cluster, name)
            command.__name__ = name
            return decorate_command(self, command)
        return self.__getattribute__(name)


class ZDOChannel(LogMixin):
    """Channel for ZDO events."""

    def __init__(self, cluster, device):
        """Initialize ZDOChannel."""
        self.name = CHANNEL_ZDO
        self._cluster = cluster
        self._zha_device = device
        self._status = ChannelStatus.CREATED
        self._unique_id = f"{str(device.ieee)}:{device.name}_ZDO"
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

    @callback
    def permit_duration(self, duration):
        """Permit handler."""

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        self._status = ChannelStatus.INITIALIZED

    async def async_configure(self):
        """Configure channel."""
        self._status = ChannelStatus.CONFIGURED

    def log(self, level, msg, *args):
        """Log a message."""
        msg = f"[%s:ZDO](%s): {msg}"
        args = (self._zha_device.nwk, self._zha_device.model) + args
        _LOGGER.log(level, msg, *args)


class ClientChannel(ZigbeeChannel):
    """Channel listener for Zigbee client (output) clusters."""

    @callback
    def attribute_updated(self, attrid, value):
        """Handle an attribute updated on this cluster."""
        self.zha_send_event(
            SIGNAL_ATTR_UPDATED,
            {
                ATTR_ATTRIBUTE_ID: attrid,
                ATTR_ATTRIBUTE_NAME: self._cluster.attributes.get(attrid, ["Unknown"])[
                    0
                ],
                ATTR_VALUE: value,
            },
        )

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle a cluster command received on this cluster."""
        if (
            self._cluster.server_commands is not None
            and self._cluster.server_commands.get(command_id) is not None
        ):
            self.zha_send_event(self._cluster.server_commands.get(command_id)[0], args)
