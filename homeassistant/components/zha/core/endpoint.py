"""Representation of a Zigbee endpoint for zha."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import functools
import logging
from typing import TYPE_CHECKING, Any, Final, TypeVar

from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.async_ import gather_with_limited_concurrency

from . import const, discovery, registries
from .cluster_handlers import ClusterHandler
from .helpers import get_zha_data

if TYPE_CHECKING:
    from zigpy import Endpoint as ZigpyEndpoint

    from .cluster_handlers import ClientClusterHandler
    from .device import ZHADevice

ATTR_DEVICE_TYPE: Final[str] = "device_type"
ATTR_PROFILE_ID: Final[str] = "profile_id"
ATTR_IN_CLUSTERS: Final[str] = "input_clusters"
ATTR_OUT_CLUSTERS: Final[str] = "output_clusters"

_LOGGER = logging.getLogger(__name__)
CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)


class Endpoint:
    """Endpoint for a zha device."""

    def __init__(self, zigpy_endpoint: ZigpyEndpoint, device: ZHADevice) -> None:
        """Initialize instance."""
        assert zigpy_endpoint is not None
        assert device is not None
        self._zigpy_endpoint: ZigpyEndpoint = zigpy_endpoint
        self._device: ZHADevice = device
        self._all_cluster_handlers: dict[str, ClusterHandler] = {}
        self._claimed_cluster_handlers: dict[str, ClusterHandler] = {}
        self._client_cluster_handlers: dict[str, ClientClusterHandler] = {}
        self._unique_id: str = f"{str(device.ieee)}-{zigpy_endpoint.endpoint_id}"

    @property
    def device(self) -> ZHADevice:
        """Return the device this endpoint belongs to."""
        return self._device

    @property
    def all_cluster_handlers(self) -> dict[str, ClusterHandler]:
        """All server cluster handlers of an endpoint."""
        return self._all_cluster_handlers

    @property
    def claimed_cluster_handlers(self) -> dict[str, ClusterHandler]:
        """Cluster handlers in use."""
        return self._claimed_cluster_handlers

    @property
    def client_cluster_handlers(self) -> dict[str, ClientClusterHandler]:
        """Return a dict of client cluster handlers."""
        return self._client_cluster_handlers

    @property
    def zigpy_endpoint(self) -> ZigpyEndpoint:
        """Return endpoint of zigpy device."""
        return self._zigpy_endpoint

    @property
    def id(self) -> int:
        """Return endpoint id."""
        return self._zigpy_endpoint.endpoint_id

    @property
    def unique_id(self) -> str:
        """Return the unique id for this endpoint."""
        return self._unique_id

    @property
    def zigbee_signature(self) -> tuple[int, dict[str, Any]]:
        """Get the zigbee signature for the endpoint this pool represents."""
        return (
            self.id,
            {
                ATTR_PROFILE_ID: f"0x{self._zigpy_endpoint.profile_id:04x}"
                if self._zigpy_endpoint.profile_id is not None
                else "",
                ATTR_DEVICE_TYPE: f"0x{self._zigpy_endpoint.device_type:04x}"
                if self._zigpy_endpoint.device_type is not None
                else "",
                ATTR_IN_CLUSTERS: [
                    f"0x{cluster_id:04x}"
                    for cluster_id in sorted(self._zigpy_endpoint.in_clusters)
                ],
                ATTR_OUT_CLUSTERS: [
                    f"0x{cluster_id:04x}"
                    for cluster_id in sorted(self._zigpy_endpoint.out_clusters)
                ],
            },
        )

    @classmethod
    def new(cls, zigpy_endpoint: ZigpyEndpoint, device: ZHADevice) -> Endpoint:
        """Create new endpoint and populate cluster handlers."""
        endpoint = cls(zigpy_endpoint, device)
        endpoint.add_all_cluster_handlers()
        endpoint.add_client_cluster_handlers()
        if not device.is_coordinator:
            discovery.PROBE.discover_entities(endpoint)
        return endpoint

    def add_all_cluster_handlers(self) -> None:
        """Create and add cluster handlers for all input clusters."""
        for cluster_id, cluster in self.zigpy_endpoint.in_clusters.items():
            cluster_handler_classes = registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.get(
                cluster_id, {None: ClusterHandler}
            )
            quirk_id = (
                self.device.quirk_id
                if self.device.quirk_id in cluster_handler_classes
                else None
            )
            cluster_handler_class = cluster_handler_classes.get(
                quirk_id, ClusterHandler
            )

            # Allow cluster handler to filter out bad matches
            if not cluster_handler_class.matches(cluster, self):
                cluster_handler_class = ClusterHandler

            _LOGGER.debug(
                "Creating cluster handler for cluster id: %s class: %s",
                cluster_id,
                cluster_handler_class,
            )

            try:
                cluster_handler = cluster_handler_class(cluster, self)
            except KeyError as err:
                _LOGGER.warning(
                    "Cluster handler %s for cluster %s on endpoint %s is invalid: %s",
                    cluster_handler_class,
                    cluster,
                    self,
                    err,
                )
                continue

            if cluster_handler.name == const.CLUSTER_HANDLER_POWER_CONFIGURATION:
                self._device.power_configuration_ch = cluster_handler
            elif cluster_handler.name == const.CLUSTER_HANDLER_IDENTIFY:
                self._device.identify_ch = cluster_handler
            elif cluster_handler.name == const.CLUSTER_HANDLER_BASIC:
                self._device.basic_ch = cluster_handler
            self._all_cluster_handlers[cluster_handler.id] = cluster_handler

    def add_client_cluster_handlers(self) -> None:
        """Create client cluster handlers for all output clusters if in the registry."""
        for (
            cluster_id,
            cluster_handler_class,
        ) in registries.CLIENT_CLUSTER_HANDLER_REGISTRY.items():
            cluster = self.zigpy_endpoint.out_clusters.get(cluster_id)
            if cluster is not None:
                cluster_handler = cluster_handler_class(cluster, self)
                self.client_cluster_handlers[cluster_handler.id] = cluster_handler

    async def async_initialize(self, from_cache: bool = False) -> None:
        """Initialize claimed cluster handlers."""
        await self._execute_handler_tasks(
            "async_initialize", from_cache, max_concurrency=1
        )

    async def async_configure(self) -> None:
        """Configure claimed cluster handlers."""
        await self._execute_handler_tasks("async_configure")

    async def _execute_handler_tasks(
        self, func_name: str, *args: Any, max_concurrency: int | None = None
    ) -> None:
        """Add a throttled cluster handler task and swallow exceptions."""
        cluster_handlers = [
            *self.claimed_cluster_handlers.values(),
            *self.client_cluster_handlers.values(),
        ]
        tasks = [getattr(ch, func_name)(*args) for ch in cluster_handlers]

        gather: Callable[..., Awaitable]

        if max_concurrency is None:
            gather = asyncio.gather
        else:
            gather = functools.partial(gather_with_limited_concurrency, max_concurrency)

        results = await gather(*tasks, return_exceptions=True)
        for cluster_handler, outcome in zip(cluster_handlers, results, strict=False):
            if isinstance(outcome, Exception):
                cluster_handler.debug(
                    "'%s' stage failed: %s", func_name, str(outcome), exc_info=outcome
                )
            else:
                cluster_handler.debug("'%s' stage succeeded", func_name)

    def async_new_entity(
        self,
        platform: Platform,
        entity_class: CALLABLE_T,
        unique_id: str,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Create a new entity."""
        from .device import DeviceStatus  # pylint: disable=import-outside-toplevel

        if self.device.status == DeviceStatus.INITIALIZED:
            return

        zha_data = get_zha_data(self.device.hass)
        zha_data.platforms[platform].append(
            (entity_class, (unique_id, self.device, cluster_handlers), kwargs or {})
        )

    @callback
    def async_send_signal(self, signal: str, *args: Any) -> None:
        """Send a signal through hass dispatcher."""
        async_dispatcher_send(self.device.hass, signal, *args)

    def send_event(self, signal: dict[str, Any]) -> None:
        """Broadcast an event from this endpoint."""
        self.device.zha_send_event(
            {
                const.ATTR_UNIQUE_ID: self.unique_id,
                const.ATTR_ENDPOINT_ID: self.id,
                **signal,
            }
        )

    def claim_cluster_handlers(self, cluster_handlers: list[ClusterHandler]) -> None:
        """Claim cluster handlers."""
        self.claimed_cluster_handlers.update({ch.id: ch for ch in cluster_handlers})

    def unclaimed_cluster_handlers(self) -> list[ClusterHandler]:
        """Return a list of available (unclaimed) cluster handlers."""
        claimed = set(self.claimed_cluster_handlers)
        available = set(self.all_cluster_handlers)
        return [
            self.all_cluster_handlers[cluster_id]
            for cluster_id in (available - claimed)
        ]
