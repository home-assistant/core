"""Channels module for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar

import zigpy.endpoint
import zigpy.zcl.clusters.closures

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import (  # noqa: F401
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
)

if TYPE_CHECKING:
    from ...entity import ZhaEntity
    from ..device import ZHADevice

_ChannelsT = TypeVar("_ChannelsT", bound="Channels")
_ChannelPoolT = TypeVar("_ChannelPoolT", bound="ChannelPool")
_ChannelsDictType = dict[str, base.ZigbeeChannel]


class Channels:
    """All discovered channels of a device."""

    def __init__(self, zha_device: ZHADevice) -> None:
        """Initialize instance."""
        self._pools: list[ChannelPool] = []
        self._power_config: base.ZigbeeChannel | None = None
        self._identify: base.ZigbeeChannel | None = None
        self._unique_id = str(zha_device.ieee)
        self._zdo_channel = base.ZDOChannel(zha_device.device.endpoints[0], zha_device)
        self._zha_device = zha_device

    @property
    def pools(self) -> list[ChannelPool]:
        """Return channel pools list."""
        return self._pools

    @property
    def power_configuration_ch(self) -> base.ZigbeeChannel | None:
        """Return power configuration channel."""
        return self._power_config

    @power_configuration_ch.setter
    def power_configuration_ch(self, channel: base.ZigbeeChannel) -> None:
        """Power configuration channel setter."""
        if self._power_config is None:
            self._power_config = channel

    @property
    def identify_ch(self) -> base.ZigbeeChannel | None:
        """Return power configuration channel."""
        return self._identify

    @identify_ch.setter
    def identify_ch(self, channel: base.ZigbeeChannel) -> None:
        """Power configuration channel setter."""
        if self._identify is None:
            self._identify = channel

    @property
    def zdo_channel(self) -> base.ZDOChannel:
        """Return ZDO channel."""
        return self._zdo_channel

    @property
    def zha_device(self) -> ZHADevice:
        """Return parent zha device."""
        return self._zha_device

    @property
    def unique_id(self) -> str:
        """Return the unique id for this channel."""
        return self._unique_id

    @property
    def zigbee_signature(self) -> dict[int, dict[str, Any]]:
        """Get the zigbee signatures for the pools in channels."""
        return {
            signature[0]: signature[1]
            for signature in [pool.zigbee_signature for pool in self.pools]
        }

    @classmethod
    def new(cls: type[_ChannelsT], zha_device: ZHADevice) -> _ChannelsT:
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
        async_dispatcher_send(
            self.zha_device.hass,
            const.ZHA_CHANNEL_MSG,
            {
                const.ATTR_TYPE: const.ZHA_CHANNEL_CFG_DONE,
            },
        )

    @callback
    def async_new_entity(
        self,
        component: str,
        entity_class: type[ZhaEntity],
        unique_id: str,
        channels: list[base.ZigbeeChannel],
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
    def zha_send_event(self, event_data: dict[str, str | int]) -> None:
        """Relay events to hass."""
        self.zha_device.hass.bus.async_fire(
            const.ZHA_EVENT,
            {
                const.ATTR_DEVICE_IEEE: str(self.zha_device.ieee),
                const.ATTR_UNIQUE_ID: self.unique_id,
                ATTR_DEVICE_ID: self.zha_device.device_id,
                **event_data,
            },
        )


class ChannelPool:
    """All channels of an endpoint."""

    def __init__(self, channels: Channels, ep_id: int) -> None:
        """Initialize instance."""
        self._all_channels: _ChannelsDictType = {}
        self._channels = channels
        self._claimed_channels: _ChannelsDictType = {}
        self._id = ep_id
        self._client_channels: dict[str, base.ClientChannel] = {}
        self._unique_id = f"{channels.unique_id}-{ep_id}"

    @property
    def all_channels(self) -> _ChannelsDictType:
        """All server channels of an endpoint."""
        return self._all_channels

    @property
    def claimed_channels(self) -> _ChannelsDictType:
        """Channels in use."""
        return self._claimed_channels

    @property
    def client_channels(self) -> dict[str, base.ClientChannel]:
        """Return a dict of client channels."""
        return self._client_channels

    @property
    def endpoint(self) -> zigpy.endpoint.Endpoint:
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
    def is_mains_powered(self) -> bool | None:
        """Device is_mains_powered."""
        return self._channels.zha_device.is_mains_powered

    @property
    def manufacturer(self) -> str:
        """Return device manufacturer."""
        return self._channels.zha_device.manufacturer

    @property
    def manufacturer_code(self) -> int | None:
        """Return device manufacturer."""
        return self._channels.zha_device.manufacturer_code

    @property
    def hass(self) -> HomeAssistant:
        """Return hass."""
        return self._channels.zha_device.hass

    @property
    def model(self) -> str:
        """Return device model."""
        return self._channels.zha_device.model

    @property
    def skip_configuration(self) -> bool:
        """Return True if device does not require channel configuration."""
        return self._channels.zha_device.skip_configuration

    @property
    def unique_id(self) -> str:
        """Return the unique id for this channel."""
        return self._unique_id

    @property
    def zigbee_signature(self) -> tuple[int, dict[str, Any]]:
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
                    for cluster_id in sorted(self.endpoint.in_clusters)
                ],
                const.ATTR_OUT_CLUSTERS: [
                    f"0x{cluster_id:04x}"
                    for cluster_id in sorted(self.endpoint.out_clusters)
                ],
            },
        )

    @classmethod
    def new(cls: type[_ChannelPoolT], channels: Channels, ep_id: int) -> _ChannelPoolT:
        """Create new channels for an endpoint."""
        pool = cls(channels, ep_id)
        pool.add_all_channels()
        pool.add_client_channels()
        if not channels.zha_device.is_coordinator:
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
                and cluster_id == zigpy.zcl.clusters.closures.DoorLock.cluster_id
                and cluster.ep_attribute == "multistate_input"
            ):
                channel_class = general.MultistateInput
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
        channels = [*self.claimed_channels.values(), *self.client_channels.values()]
        tasks = [getattr(ch, func_name)(*args) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for channel, outcome in zip(channels, results):
            if isinstance(outcome, Exception):
                channel.warning(
                    "'%s' stage failed: %s", func_name, str(outcome), exc_info=outcome
                )
                continue
            channel.debug("'%s' stage succeeded", func_name)

    @callback
    def async_new_entity(
        self,
        component: str,
        entity_class: type[ZhaEntity],
        unique_id: str,
        channels: list[base.ZigbeeChannel],
    ):
        """Signal new entity addition."""
        self._channels.async_new_entity(component, entity_class, unique_id, channels)

    @callback
    def async_send_signal(self, signal: str, *args: Any) -> None:
        """Send a signal through hass dispatcher."""
        self._channels.async_send_signal(signal, *args)

    @callback
    def claim_channels(self, channels: list[base.ZigbeeChannel]) -> None:
        """Claim a channel."""
        self.claimed_channels.update({ch.id: ch for ch in channels})

    @callback
    def unclaimed_channels(self) -> list[base.ZigbeeChannel]:
        """Return a list of available (unclaimed) channels."""
        claimed = set(self.claimed_channels)
        available = set(self.all_channels)
        return [self.all_channels[chan_id] for chan_id in (available - claimed)]

    @callback
    def zha_send_event(self, event_data: dict[str, Any]) -> None:
        """Relay events to hass."""
        self._channels.zha_send_event(
            {
                const.ATTR_UNIQUE_ID: self.unique_id,
                const.ATTR_ENDPOINT_ID: self.id,
                **event_data,
            }
        )
