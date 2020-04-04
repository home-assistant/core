"""Channels module for Zigbee Home Automation."""
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import (  # noqa: F401 # pylint: disable=unused-import
    base,
    closures,
    general,
    homeautomation,
    hvac,
    lighting,
    lightlink,
    manufacturerspecific,
    measurement,
    protocol,
    security,
    smartenergy,
)
from .. import (
    const,
    device as zha_core_device,
    discovery as zha_disc,
    registries as zha_regs,
    typing as zha_typing,
)

_LOGGER = logging.getLogger(__name__)
ChannelsDict = Dict[str, zha_typing.ChannelType]


class Channels:
    """All discovered channels of a device."""

    def __init__(self, zha_device: zha_typing.ZhaDeviceType) -> None:
        """Initialize instance."""
        self._pools: List[zha_typing.ChannelPoolType] = []
        self._power_config = None
        self._identify = None
        self._semaphore = asyncio.Semaphore(3)
        self._unique_id = str(zha_device.ieee)
        self._zdo_channel = base.ZDOChannel(zha_device.device.endpoints[0], zha_device)
        self._zha_device = zha_device

    @property
    def pools(self) -> List["ChannelPool"]:
        """Return channel pools list."""
        return self._pools

    @property
    def power_configuration_ch(self) -> zha_typing.ChannelType:
        """Return power configuration channel."""
        return self._power_config

    @power_configuration_ch.setter
    def power_configuration_ch(self, channel: zha_typing.ChannelType) -> None:
        """Power configuration channel setter."""
        if self._power_config is None:
            self._power_config = channel

    @property
    def identify_ch(self) -> zha_typing.ChannelType:
        """Return power configuration channel."""
        return self._identify

    @identify_ch.setter
    def identify_ch(self, channel: zha_typing.ChannelType) -> None:
        """Power configuration channel setter."""
        if self._identify is None:
            self._identify = channel

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """Return semaphore for concurrent tasks."""
        return self._semaphore

    @property
    def zdo_channel(self) -> zha_typing.ZDOChannelType:
        """Return ZDO channel."""
        return self._zdo_channel

    @property
    def zha_device(self) -> zha_typing.ZhaDeviceType:
        """Return parent zha device."""
        return self._zha_device

    @property
    def unique_id(self):
        """Return the unique id for this channel."""
        return self._unique_id

    @classmethod
    def new(cls, zha_device: zha_typing.ZhaDeviceType) -> "Channels":
        """Create new instance."""
        channels = cls(zha_device)
        for ep_id in sorted(zha_device.device.endpoints):
            channels.add_pool(ep_id)
        return channels

    def add_pool(self, ep_id: int) -> None:
        """Add channels for a specific endpoint."""
        if ep_id == 0:
            return
        self._pools.append(ChannelPool.new(self, ep_id))

    async def async_initialize(self, from_cache: bool = False) -> None:
        """Initialize claimed channels."""
        await self.zdo_channel.async_initialize(from_cache)
        self.zdo_channel.debug("'async_initialize' stage succeeded")
        await asyncio.gather(
            *(pool.async_initialize(from_cache) for pool in self.pools)
        )

    async def async_configure(self) -> None:
        """Configure claimed channels."""
        await self.zdo_channel.async_configure()
        self.zdo_channel.debug("'async_configure' stage succeeded")
        await asyncio.gather(*(pool.async_configure() for pool in self.pools))

    @callback
    def async_new_entity(
        self,
        component: str,
        entity_class: zha_typing.CALLABLE_T,
        unique_id: str,
        channels: List[zha_typing.ChannelType],
    ):
        """Signal new entity addition."""
        if self.zha_device.status == zha_core_device.DeviceStatus.INITIALIZED:
            return

        self.zha_device.hass.data[const.DATA_ZHA][component].append(
            (entity_class, (unique_id, self.zha_device, channels))
        )

    @callback
    def async_send_signal(self, signal: str, *args: Any) -> None:
        """Send a signal through hass dispatcher."""
        async_dispatcher_send(self.zha_device.hass, signal, *args)

    @callback
    def zha_send_event(self, event_data: Dict[str, Union[str, int]]) -> None:
        """Relay events to hass."""
        self.zha_device.hass.bus.async_fire(
            "zha_event",
            {
                const.ATTR_DEVICE_IEEE: str(self.zha_device.ieee),
                const.ATTR_UNIQUE_ID: self.unique_id,
                **event_data,
            },
        )

    @callback
    def async_get_zigbee_signature(self) -> Dict[int, Dict[str, Any]]:
        """Get the zigbee signatures for the pools in channels."""
        return {
            signature[0]: signature[1]
            for signature in [pool.async_get_zigbee_signature() for pool in self.pools]
        }


class ChannelPool:
    """All channels of an endpoint."""

    def __init__(self, channels: Channels, ep_id: int):
        """Initialize instance."""
        self._all_channels: ChannelsDict = {}
        self._channels: Channels = channels
        self._claimed_channels: ChannelsDict = {}
        self._id: int = ep_id
        self._client_channels: Dict[str, zha_typing.ClientChannelType] = {}
        self._unique_id: str = f"{channels.unique_id}-{ep_id}"

    @property
    def all_channels(self) -> ChannelsDict:
        """All server channels of an endpoint."""
        return self._all_channels

    @property
    def claimed_channels(self) -> ChannelsDict:
        """Channels in use."""
        return self._claimed_channels

    @property
    def client_channels(self) -> Dict[str, zha_typing.ClientChannelType]:
        """Return a dict of client channels."""
        return self._client_channels

    @property
    def endpoint(self) -> zha_typing.ZigpyEndpointType:
        """Return endpoint of zigpy device."""
        return self._channels.zha_device.device.endpoints[self.id]

    @property
    def id(self) -> int:
        """Return endpoint id."""
        return self._id

    @property
    def nwk(self) -> int:
        """Device NWK for logging."""
        return self._channels.zha_device.nwk

    @property
    def is_mains_powered(self) -> bool:
        """Device is_mains_powered."""
        return self._channels.zha_device.is_mains_powered

    @property
    def manufacturer(self) -> Optional[str]:
        """Return device manufacturer."""
        return self._channels.zha_device.manufacturer

    @property
    def manufacturer_code(self) -> Optional[int]:
        """Return device manufacturer."""
        return self._channels.zha_device.manufacturer_code

    @property
    def hass(self):
        """Return hass."""
        return self._channels.zha_device.hass

    @property
    def model(self) -> Optional[str]:
        """Return device model."""
        return self._channels.zha_device.model

    @property
    def skip_configuration(self) -> bool:
        """Return True if device does not require channel configuration."""
        return self._channels.zha_device.skip_configuration

    @property
    def unique_id(self):
        """Return the unique id for this channel."""
        return self._unique_id

    @classmethod
    def new(cls, channels: Channels, ep_id: int) -> "ChannelPool":
        """Create new channels for an endpoint."""
        pool = cls(channels, ep_id)
        pool.add_all_channels()
        pool.add_client_channels()
        zha_disc.PROBE.discover_entities(pool)
        return pool

    @callback
    def add_all_channels(self) -> None:
        """Create and add channels for all input clusters."""
        for cluster_id, cluster in self.endpoint.in_clusters.items():
            channel_class = zha_regs.ZIGBEE_CHANNEL_REGISTRY.get(
                cluster_id, base.ZigbeeChannel
            )
            # really ugly hack to deal with xiaomi using the door lock cluster
            # incorrectly.
            if (
                hasattr(cluster, "ep_attribute")
                and cluster.ep_attribute == "multistate_input"
            ):
                channel_class = base.ZigbeeChannel
            # end of ugly hack
            channel = channel_class(cluster, self)
            if channel.name == const.CHANNEL_POWER_CONFIGURATION:
                if (
                    self._channels.power_configuration_ch
                    or self._channels.zha_device.is_mains_powered
                ):
                    # on power configuration channel per device
                    continue
                self._channels.power_configuration_ch = channel
            elif channel.name == const.CHANNEL_IDENTIFY:
                self._channels.identify_ch = channel

            self.all_channels[channel.id] = channel

    @callback
    def add_client_channels(self) -> None:
        """Create client channels for all output clusters if in the registry."""
        for cluster_id, channel_class in zha_regs.CLIENT_CHANNELS_REGISTRY.items():
            cluster = self.endpoint.out_clusters.get(cluster_id)
            if cluster is not None:
                channel = channel_class(cluster, self)
                self.client_channels[channel.id] = channel

    async def async_initialize(self, from_cache: bool = False) -> None:
        """Initialize claimed channels."""
        await self._execute_channel_tasks("async_initialize", from_cache)

    async def async_configure(self) -> None:
        """Configure claimed channels."""
        await self._execute_channel_tasks("async_configure")

    async def _execute_channel_tasks(self, func_name: str, *args: Any) -> None:
        """Add a throttled channel task and swallow exceptions."""

        async def _throttle(coro):
            async with self._channels.semaphore:
                return await coro

        channels = [*self.claimed_channels.values(), *self.client_channels.values()]
        tasks = [_throttle(getattr(ch, func_name)(*args)) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for channel, outcome in zip(channels, results):
            if isinstance(outcome, Exception):
                channel.warning("'%s' stage failed: %s", func_name, str(outcome))
                continue
            channel.debug("'%s' stage succeeded", func_name)

    @callback
    def async_new_entity(
        self,
        component: str,
        entity_class: zha_typing.CALLABLE_T,
        unique_id: str,
        channels: List[zha_typing.ChannelType],
    ):
        """Signal new entity addition."""
        self._channels.async_new_entity(component, entity_class, unique_id, channels)

    @callback
    def async_send_signal(self, signal: str, *args: Any) -> None:
        """Send a signal through hass dispatcher."""
        self._channels.async_send_signal(signal, *args)

    @callback
    def claim_channels(self, channels: List[zha_typing.ChannelType]) -> None:
        """Claim a channel."""
        self.claimed_channels.update({ch.id: ch for ch in channels})

    @callback
    def unclaimed_channels(self) -> List[zha_typing.ChannelType]:
        """Return a list of available (unclaimed) channels."""
        claimed = set(self.claimed_channels)
        available = set(self.all_channels)
        return [self.all_channels[chan_id] for chan_id in (available - claimed)]

    @callback
    def zha_send_event(self, event_data: Dict[str, Union[str, int]]) -> None:
        """Relay events to hass."""
        self._channels.zha_send_event(
            {
                const.ATTR_UNIQUE_ID: self.unique_id,
                const.ATTR_ENDPOINT_ID: self.id,
                **event_data,
            }
        )

    @callback
    def async_get_zigbee_signature(self) -> Tuple[int, Dict[str, Any]]:
        """Get the zigbee signature for the endpoint this pool represents."""
        return (
            self.endpoint.endpoint_id,
            {
                const.ATTR_PROFILE_ID: self.endpoint.profile_id,
                const.ATTR_DEVICE_TYPE: f"0x{self.endpoint.device_type:04x}"
                if self.endpoint.device_type is not None
                else "",
                const.ATTR_IN_CLUSTERS: [
                    f"0x{cluster_id:04x}"
                    for cluster_id in self.endpoint.in_clusters.keys()
                ],
                const.ATTR_OUT_CLUSTERS: [
                    f"0x{cluster_id:04x}"
                    for cluster_id in self.endpoint.out_clusters.keys()
                ],
            },
        )
