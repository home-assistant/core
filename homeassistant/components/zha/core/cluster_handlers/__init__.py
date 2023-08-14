"""Cluster handlers module for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from enum import Enum
import functools
import logging
from typing import TYPE_CHECKING, Any, ParamSpec, TypedDict

import zigpy.exceptions
import zigpy.util
import zigpy.zcl
from zigpy.zcl.foundation import (
    CommandSchema,
    ConfigureReportingResponseRecord,
    Status,
    ZCLAttributeDef,
)

from homeassistant.const import ATTR_COMMAND
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import (
    ATTR_ARGS,
    ATTR_ATTRIBUTE_ID,
    ATTR_ATTRIBUTE_NAME,
    ATTR_CLUSTER_ID,
    ATTR_PARAMS,
    ATTR_TYPE,
    ATTR_UNIQUE_ID,
    ATTR_VALUE,
    CLUSTER_HANDLER_ZDO,
    REPORT_CONFIG_ATTR_PER_REQ,
    SIGNAL_ATTR_UPDATED,
    ZHA_CLUSTER_HANDLER_MSG,
    ZHA_CLUSTER_HANDLER_MSG_BIND,
    ZHA_CLUSTER_HANDLER_MSG_CFG_RPT,
    ZHA_CLUSTER_HANDLER_MSG_DATA,
    ZHA_CLUSTER_HANDLER_READS_PER_REQ,
)
from ..helpers import LogMixin, retryable_req, safe_read

if TYPE_CHECKING:
    from ..endpoint import Endpoint

_LOGGER = logging.getLogger(__name__)
RETRYABLE_REQUEST_DECORATOR = zigpy.util.retryable_request(tries=3)


_P = ParamSpec("_P")
_FuncType = Callable[_P, Awaitable[Any]]
_ReturnFuncType = Callable[_P, Coroutine[Any, Any, Any]]


def retry_request(func: _FuncType[_P]) -> _ReturnFuncType[_P]:
    """Send a request with retries and wrap expected zigpy exceptions."""

    @functools.wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Any:
        try:
            return await RETRYABLE_REQUEST_DECORATOR(func)(*args, **kwargs)
        except asyncio.TimeoutError as exc:
            raise HomeAssistantError(
                "Failed to send request: device did not respond"
            ) from exc
        except zigpy.exceptions.ZigbeeException as exc:
            message = "Failed to send request"

            if str(exc):
                message = f"{message}: {exc}"

            raise HomeAssistantError(message) from exc

    return wrapper


class AttrReportConfig(TypedDict, total=True):
    """Configuration to report for the attributes."""

    # An attribute name
    attr: str
    # The config for the attribute reporting configuration consists of a tuple for
    # (minimum_reported_time_interval_s, maximum_reported_time_interval_s, value_delta)
    config: tuple[int, int, int | float]


def parse_and_log_command(cluster_handler, tsn, command_id, args):
    """Parse and log a zigbee cluster command."""
    try:
        name = cluster_handler.cluster.server_commands[command_id].name
    except KeyError:
        name = f"0x{command_id:02X}"

    cluster_handler.debug(
        "received '%s' command with %s args on cluster_id '%s' tsn '%s'",
        name,
        args,
        cluster_handler.cluster.cluster_id,
        tsn,
    )
    return name


class ClusterHandlerStatus(Enum):
    """Status of a cluster handler."""

    CREATED = 1
    CONFIGURED = 2
    INITIALIZED = 3


class ClusterHandler(LogMixin):
    """Base cluster handler for a Zigbee cluster."""

    REPORT_CONFIG: tuple[AttrReportConfig, ...] = ()
    BIND: bool = True

    # Dict of attributes to read on cluster handler initialization.
    # Dict keys -- attribute ID or names, with bool value indicating whether a cached
    # attribute read is acceptable.
    ZCL_INIT_ATTRS: dict[str, bool] = {}

    def __init__(self, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> None:
        """Initialize ClusterHandler."""
        self._generic_id = f"cluster_handler_0x{cluster.cluster_id:04x}"
        self._endpoint: Endpoint = endpoint
        self._cluster = cluster
        self._id = f"{endpoint.id}:0x{cluster.cluster_id:04x}"
        unique_id = endpoint.unique_id.replace("-", ":")
        self._unique_id = f"{unique_id}:0x{cluster.cluster_id:04x}"
        if not hasattr(self, "_value_attribute") and self.REPORT_CONFIG:
            attr_def: ZCLAttributeDef = self.cluster.attributes_by_name[
                self.REPORT_CONFIG[0]["attr"]
            ]
            self.value_attribute = attr_def.id
        self._status = ClusterHandlerStatus.CREATED
        self._cluster.add_listener(self)
        self.data_cache: dict[str, Enum] = {}

    @classmethod
    def matches(cls, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> bool:
        """Filter the cluster match for specific devices."""
        return True

    @property
    def id(self) -> str:
        """Return cluster handler id unique for this device only."""
        return self._id

    @property
    def generic_id(self):
        """Return the generic id for this cluster handler."""
        return self._generic_id

    @property
    def unique_id(self):
        """Return the unique id for this cluster handler."""
        return self._unique_id

    @property
    def cluster(self):
        """Return the zigpy cluster for this cluster handler."""
        return self._cluster

    @property
    def name(self) -> str:
        """Return friendly name."""
        return self.cluster.ep_attribute or self._generic_id

    @property
    def status(self):
        """Return the status of the cluster handler."""
        return self._status

    def __hash__(self) -> int:
        """Make this a hashable."""
        return hash(self._unique_id)

    @callback
    def async_send_signal(self, signal: str, *args: Any) -> None:
        """Send a signal through hass dispatcher."""
        self._endpoint.async_send_signal(signal, *args)

    async def bind(self):
        """Bind a zigbee cluster.

        This also swallows ZigbeeException exceptions that are thrown when
        devices are unreachable.
        """
        try:
            res = await self.cluster.bind()
            self.debug("bound '%s' cluster: %s", self.cluster.ep_attribute, res[0])
            async_dispatcher_send(
                self._endpoint.device.hass,
                ZHA_CLUSTER_HANDLER_MSG,
                {
                    ATTR_TYPE: ZHA_CLUSTER_HANDLER_MSG_BIND,
                    ZHA_CLUSTER_HANDLER_MSG_DATA: {
                        "cluster_name": self.cluster.name,
                        "cluster_id": self.cluster.cluster_id,
                        "success": res[0] == 0,
                    },
                },
            )
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                "Failed to bind '%s' cluster: %s",
                self.cluster.ep_attribute,
                str(ex),
                exc_info=ex,
            )
            async_dispatcher_send(
                self._endpoint.device.hass,
                ZHA_CLUSTER_HANDLER_MSG,
                {
                    ATTR_TYPE: ZHA_CLUSTER_HANDLER_MSG_BIND,
                    ZHA_CLUSTER_HANDLER_MSG_DATA: {
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
        if (
            self.cluster.cluster_id >= 0xFC00
            and self._endpoint.device.manufacturer_code
        ):
            kwargs["manufacturer"] = self._endpoint.device.manufacturer_code

        for attr_report in self.REPORT_CONFIG:
            attr, config = attr_report["attr"], attr_report["config"]

            try:
                attr_name = self.cluster.find_attribute(attr).name
            except KeyError:
                attr_name = attr

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
            self._endpoint.device.hass,
            ZHA_CLUSTER_HANDLER_MSG,
            {
                ATTR_TYPE: ZHA_CLUSTER_HANDLER_MSG_CFG_RPT,
                ZHA_CLUSTER_HANDLER_MSG_DATA: {
                    "cluster_name": self.cluster.name,
                    "cluster_id": self.cluster.cluster_id,
                    "attributes": event_data,
                },
            },
        )

    def _configure_reporting_status(
        self, attrs: dict[str, tuple[int, int, float | int]], res: list | tuple
    ) -> None:
        """Parse configure reporting result."""
        if isinstance(res, (Exception, ConfigureReportingResponseRecord)):
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
            self.cluster.find_attribute(record.attrid).name
            for record in res
            if record.status != Status.SUCCESS
        ]
        self.debug(
            "Successfully configured reporting for '%s' on '%s' cluster",
            set(attrs) - set(failed),
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
        if not self._endpoint.device.skip_configuration:
            if self.BIND:
                self.debug("Performing cluster binding")
                await self.bind()
            if self.cluster.is_server:
                self.debug("Configuring cluster attribute reporting")
                await self.configure_reporting()
            ch_specific_cfg = getattr(
                self, "async_configure_cluster_handler_specific", None
            )
            if ch_specific_cfg:
                self.debug("Performing cluster handler specific configuration")
                await ch_specific_cfg()
            self.debug("finished cluster handler configuration")
        else:
            self.debug("skipping cluster handler configuration")
        self._status = ClusterHandlerStatus.CONFIGURED

    @retryable_req(delays=(1, 1, 3))
    async def async_initialize(self, from_cache: bool) -> None:
        """Initialize cluster handler."""
        if not from_cache and self._endpoint.device.skip_configuration:
            self.debug("Skipping cluster handler initialization")
            self._status = ClusterHandlerStatus.INITIALIZED
            return

        self.debug("initializing cluster handler: from_cache: %s", from_cache)
        cached = [a for a, cached in self.ZCL_INIT_ATTRS.items() if cached]
        uncached = [a for a, cached in self.ZCL_INIT_ATTRS.items() if not cached]
        uncached.extend([cfg["attr"] for cfg in self.REPORT_CONFIG])

        if cached:
            self.debug("initializing cached cluster handler attributes: %s", cached)
            await self._get_attributes(
                True, cached, from_cache=True, only_cache=from_cache
            )
        if uncached:
            self.debug(
                "initializing uncached cluster handler attributes: %s - from cache[%s]",
                uncached,
                from_cache,
            )
            await self._get_attributes(
                True, uncached, from_cache=from_cache, only_cache=from_cache
            )

        ch_specific_init = getattr(
            self, "async_initialize_cluster_handler_specific", None
        )
        if ch_specific_init:
            self.debug(
                "Performing cluster handler specific initialization: %s", uncached
            )
            await ch_specific_init(from_cache=from_cache)

        self.debug("finished cluster handler initialization")
        self._status = ClusterHandlerStatus.INITIALIZED

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
        """Handle attribute updates on this cluster."""
        self.async_send_signal(
            f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
            attrid,
            self._get_attribute_name(attrid),
            value,
        )

    @callback
    def zdo_command(self, *args, **kwargs):
        """Handle ZDO commands on this cluster."""

    @callback
    def zha_send_event(self, command: str, arg: list | dict | CommandSchema) -> None:
        """Relay events to hass."""

        args: list | dict
        if isinstance(arg, CommandSchema):
            args = [a for a in arg if a is not None]
            params = arg.as_dict()
        elif isinstance(arg, (list, dict)):
            # Quirks can directly send lists and dicts to ZHA this way
            args = arg
            params = {}
        else:
            raise TypeError(f"Unexpected zha_send_event {command!r} argument: {arg!r}")

        self._endpoint.send_event(
            {
                ATTR_UNIQUE_ID: self.unique_id,
                ATTR_CLUSTER_ID: self.cluster.cluster_id,
                ATTR_COMMAND: command,
                # Maintain backwards compatibility with the old zigpy response format
                ATTR_ARGS: args,
                ATTR_PARAMS: params,
            }
        )

    async def async_update(self):
        """Retrieve latest state from cluster."""

    def _get_attribute_name(self, attrid: int) -> str | int:
        if attrid not in self.cluster.attributes:
            return attrid

        return self.cluster.attributes[attrid].name

    async def get_attribute_value(self, attribute, from_cache=True):
        """Get the value for an attribute."""
        manufacturer = None
        manufacturer_code = self._endpoint.device.manufacturer_code
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

    async def _get_attributes(
        self,
        raise_exceptions: bool,
        attributes: list[str],
        from_cache: bool = True,
        only_cache: bool = True,
    ) -> dict[int | str, Any]:
        """Get the values for a list of attributes."""
        manufacturer = None
        manufacturer_code = self._endpoint.device.manufacturer_code
        if self.cluster.cluster_id >= 0xFC00 and manufacturer_code:
            manufacturer = manufacturer_code
        chunk = attributes[:ZHA_CLUSTER_HANDLER_READS_PER_REQ]
        rest = attributes[ZHA_CLUSTER_HANDLER_READS_PER_REQ:]
        result = {}
        while chunk:
            try:
                self.debug("Reading attributes in chunks: %s", chunk)
                read, _ = await self.cluster.read_attributes(
                    chunk,
                    allow_cache=from_cache,
                    only_cache=only_cache,
                    manufacturer=manufacturer,
                )
                result.update(read)
            except (asyncio.TimeoutError, zigpy.exceptions.ZigbeeException) as ex:
                self.debug(
                    "failed to get attributes '%s' on '%s' cluster: %s",
                    chunk,
                    self.cluster.ep_attribute,
                    str(ex),
                )
                if raise_exceptions:
                    raise
            chunk = rest[:ZHA_CLUSTER_HANDLER_READS_PER_REQ]
            rest = rest[ZHA_CLUSTER_HANDLER_READS_PER_REQ:]
        return result

    get_attributes = functools.partialmethod(_get_attributes, False)

    async def write_attributes_safe(
        self, attributes: dict[str, Any], manufacturer: int | None = None
    ) -> None:
        """Wrap `write_attributes` to throw an exception on attribute write failure."""

        res = await self.write_attributes(attributes, manufacturer=manufacturer)

        for record in res[0]:
            if record.status != Status.SUCCESS:
                try:
                    name = self.cluster.attributes_by_id[record.attrid]
                    value = attributes.get(name, "unknown")
                except KeyError:
                    name = f"0x{record.attrid:04x}"
                    value = "unknown"

                raise HomeAssistantError(
                    f"Failed to write attribute {name}={value}: {record.status}",
                )

    def log(self, level, msg, *args, **kwargs):
        """Log a message."""
        msg = f"[%s:%s]: {msg}"
        args = (self._endpoint.device.nwk, self._id) + args
        _LOGGER.log(level, msg, *args, **kwargs)

    def __getattr__(self, name):
        """Get attribute or a decorated cluster command."""
        if hasattr(self._cluster, name) and callable(getattr(self._cluster, name)):
            command = getattr(self._cluster, name)
            wrapped_command = retry_request(command)
            wrapped_command.__name__ = name

            return wrapped_command
        return self.__getattribute__(name)


class ZDOClusterHandler(LogMixin):
    """Cluster handler for ZDO events."""

    def __init__(self, device):
        """Initialize ZDOClusterHandler."""
        self.name = CLUSTER_HANDLER_ZDO
        self._cluster = device.device.endpoints[0]
        self._zha_device = device
        self._status = ClusterHandlerStatus.CREATED
        self._unique_id = f"{str(device.ieee)}:{device.name}_ZDO"
        self._cluster.add_listener(self)

    @property
    def unique_id(self):
        """Return the unique id for this cluster handler."""
        return self._unique_id

    @property
    def cluster(self):
        """Return the aigpy cluster for this cluster handler."""
        return self._cluster

    @property
    def status(self):
        """Return the status of the cluster handler."""
        return self._status

    @callback
    def device_announce(self, zigpy_device):
        """Device announce handler."""

    @callback
    def permit_duration(self, duration):
        """Permit handler."""

    async def async_initialize(self, from_cache):
        """Initialize cluster handler."""
        self._status = ClusterHandlerStatus.INITIALIZED

    async def async_configure(self):
        """Configure cluster handler."""
        self._status = ClusterHandlerStatus.CONFIGURED

    def log(self, level, msg, *args, **kwargs):
        """Log a message."""
        msg = f"[%s:ZDO](%s): {msg}"
        args = (self._zha_device.nwk, self._zha_device.model) + args
        _LOGGER.log(level, msg, *args, **kwargs)


class ClientClusterHandler(ClusterHandler):
    """ClusterHandler for Zigbee client (output) clusters."""

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
        """Handle an attribute updated on this cluster."""

        try:
            attr_name = self._cluster.attributes[attrid].name
        except KeyError:
            attr_name = "Unknown"

        self.zha_send_event(
            SIGNAL_ATTR_UPDATED,
            {
                ATTR_ATTRIBUTE_ID: attrid,
                ATTR_ATTRIBUTE_NAME: attr_name,
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
            self.zha_send_event(self._cluster.server_commands[command_id].name, args)
