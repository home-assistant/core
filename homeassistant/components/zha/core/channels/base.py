"""Base classes for channels."""
from __future__ import annotations

import asyncio
from enum import Enum
from functools import partialmethod, wraps
import logging
from typing import Any

import zigpy.exceptions
from zigpy.zcl.foundation import Status

from homeassistant.const import ATTR_COMMAND
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .. import typing as zha_typing
from ..const import (
    ATTR_ARGS,
    ATTR_ATTRIBUTE_ID,
    ATTR_ATTRIBUTE_NAME,
    ATTR_CLUSTER_ID,
    ATTR_TYPE,
    ATTR_UNIQUE_ID,
    ATTR_VALUE,
    CHANNEL_ZDO,
    REPORT_CONFIG_ATTR_PER_REQ,
    SIGNAL_ATTR_UPDATED,
    ZHA_CHANNEL_MSG,
    ZHA_CHANNEL_MSG_BIND,
    ZHA_CHANNEL_MSG_CFG_RPT,
    ZHA_CHANNEL_MSG_DATA,
    ZHA_CHANNEL_READS_PER_REQ,
)
from ..helpers import LogMixin, retryable_req, safe_read

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

    REPORT_CONFIG: tuple[dict[int | str, tuple[int, int, int | float]]] = ()
    BIND: bool = True

    # Dict of attributes to read on channel initialization.
    # Dict keys -- attribute ID or names, with bool value indicating whether a cached
    # attribute read is acceptable.
    ZCL_INIT_ATTRS: dict[int | str, bool] = {}

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
        if not hasattr(self, "_value_attribute") and self.REPORT_CONFIG:
            attr = self.REPORT_CONFIG[0].get("attr")
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

    def __hash__(self) -> int:
        """Make this a hashable."""
        return hash(self._unique_id)

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
            async_dispatcher_send(
                self._ch_pool.hass,
                ZHA_CHANNEL_MSG,
                {
                    ATTR_TYPE: ZHA_CHANNEL_MSG_BIND,
                    ZHA_CHANNEL_MSG_DATA: {
                        "cluster_name": self.cluster.name,
                        "cluster_id": self.cluster.cluster_id,
                        "success": res[0] == 0,
                    },
                },
            )
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                "Failed to bind '%s' cluster: %s", self.cluster.ep_attribute, str(ex)
            )
            async_dispatcher_send(
                self._ch_pool.hass,
                ZHA_CHANNEL_MSG,
                {
                    ATTR_TYPE: ZHA_CHANNEL_MSG_BIND,
                    ZHA_CHANNEL_MSG_DATA: {
                        "cluster_name": self.cluster.name,
                        "cluster_id": self.cluster.cluster_id,
                        "success": False,
                    },
                },
            )

    async def configure_reporting(self) -> None:
        """Configure attribute reporting for a cluster.

        This also swallows ZigbeeException exceptions that are thrown when
        devices are unreachable.
        """
        event_data = {}
        kwargs = {}
        if self.cluster.cluster_id >= 0xFC00 and self._ch_pool.manufacturer_code:
            kwargs["manufacturer"] = self._ch_pool.manufacturer_code

        for attr_report in self.REPORT_CONFIG:
            attr, config = attr_report["attr"], attr_report["config"]
            attr_name = self.cluster.attributes.get(attr, [attr])[0]
            event_data[attr_name] = {
                "min": config[0],
                "max": config[1],
                "id": attr,
                "name": attr_name,
                "change": config[2],
                "success": False,
            }

        to_configure = [*self.REPORT_CONFIG]
        chunk, rest = (
            to_configure[:REPORT_CONFIG_ATTR_PER_REQ],
            to_configure[REPORT_CONFIG_ATTR_PER_REQ:],
        )
        while chunk:
            reports = {rec["attr"]: rec["config"] for rec in chunk}
            try:
                res = await self.cluster.configure_reporting_multiple(reports, **kwargs)
                self._configure_reporting_status(reports, res[0])
                # if we get a response, then it's a success
                for attr_stat in event_data.values():
                    attr_stat["success"] = True
            except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
                self.debug(
                    "failed to set reporting on '%s' cluster for: %s",
                    self.cluster.ep_attribute,
                    str(ex),
                )
                break
            chunk, rest = (
                rest[:REPORT_CONFIG_ATTR_PER_REQ],
                rest[REPORT_CONFIG_ATTR_PER_REQ:],
            )

        async_dispatcher_send(
            self._ch_pool.hass,
            ZHA_CHANNEL_MSG,
            {
                ATTR_TYPE: ZHA_CHANNEL_MSG_CFG_RPT,
                ZHA_CHANNEL_MSG_DATA: {
                    "cluster_name": self.cluster.name,
                    "cluster_id": self.cluster.cluster_id,
                    "attributes": event_data,
                },
            },
        )

    def _configure_reporting_status(
        self, attrs: dict[int | str, tuple], res: list | tuple
    ) -> None:
        """Parse configure reporting result."""
        if not isinstance(res, list):
            # assume default response
            self.debug(
                "attr reporting for '%s' on '%s': %s",
                attrs,
                self.name,
                res,
            )
            return
        if res[0].status == Status.SUCCESS and len(res) == 1:
            self.debug(
                "Successfully configured reporting for '%s' on '%s' cluster: %s",
                attrs,
                self.name,
                res,
            )
            return

        failed = [
            self.cluster.attributes.get(r.attrid, [r.attrid])[0]
            for r in res
            if r.status != Status.SUCCESS
        ]
        attrs = {self.cluster.attributes.get(r, [r])[0] for r in attrs}
        self.debug(
            "Successfully configured reporting for '%s' on '%s' cluster",
            attrs - set(failed),
            self.name,
        )
        self.debug(
            "Failed to configure reporting for '%s' on '%s' cluster: %s",
            failed,
            self.name,
            res,
        )

    async def async_configure(self) -> None:
        """Set cluster binding and attribute reporting."""
        if not self._ch_pool.skip_configuration:
            if self.BIND:
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

    @retryable_req(delays=(1, 1, 3))
    async def async_initialize(self, from_cache: bool) -> None:
        """Initialize channel."""
        if not from_cache and self._ch_pool.skip_configuration:
            self._status = ChannelStatus.INITIALIZED
            return

        self.debug("initializing channel: from_cache: %s", from_cache)
        cached = [a for a, cached in self.ZCL_INIT_ATTRS.items() if cached]
        uncached = [a for a, cached in self.ZCL_INIT_ATTRS.items() if not cached]
        uncached.extend([cfg["attr"] for cfg in self.REPORT_CONFIG])

        if cached:
            await self._get_attributes(True, cached, from_cache=True)
        if uncached:
            await self._get_attributes(True, uncached, from_cache=from_cache)

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

    async def _get_attributes(
        self,
        raise_exceptions: bool,
        attributes: list[int | str],
        from_cache: bool = True,
    ) -> dict[int | str, Any]:
        """Get the values for a list of attributes."""
        manufacturer = None
        manufacturer_code = self._ch_pool.manufacturer_code
        if self.cluster.cluster_id >= 0xFC00 and manufacturer_code:
            manufacturer = manufacturer_code
        chunk = attributes[:ZHA_CHANNEL_READS_PER_REQ]
        rest = attributes[ZHA_CHANNEL_READS_PER_REQ:]
        result = {}
        while chunk:
            try:
                read, _ = await self.cluster.read_attributes(
                    attributes,
                    allow_cache=from_cache,
                    only_cache=from_cache and not self._ch_pool.is_mains_powered,
                    manufacturer=manufacturer,
                )
                result.update(read)
            except (asyncio.TimeoutError, zigpy.exceptions.ZigbeeException) as ex:
                self.debug(
                    "failed to get attributes '%s' on '%s' cluster: %s",
                    attributes,
                    self.cluster.ep_attribute,
                    str(ex),
                )
                if raise_exceptions:
                    raise
            chunk = rest[:ZHA_CHANNEL_READS_PER_REQ]
            rest = rest[ZHA_CHANNEL_READS_PER_REQ:]
        return result

    get_attributes = partialmethod(_get_attributes, False)

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
