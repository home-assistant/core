"""Channels module for Zigbee Home Automation."""
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union

import voluptuous as vol
import zhaquirks.const as zhaquirks_const
import zigpy.zcl.clusters.closures

import homeassistant.const as ha_const
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

ChannelsDict = Dict[str, zha_typing.ChannelType]

INTERACTION_TARGETS = {
    zhaquirks_const.BUTTON_1: ha_const.TARGET_BUTTON_1,
    zhaquirks_const.BUTTON_2: ha_const.TARGET_BUTTON_2,
    zhaquirks_const.BUTTON_3: ha_const.TARGET_BUTTON_3,
    zhaquirks_const.BUTTON_4: ha_const.TARGET_BUTTON_4,
    zhaquirks_const.BUTTON_5: ha_const.TARGET_BUTTON_5,
    zhaquirks_const.BUTTON_6: ha_const.TARGET_BUTTON_6,
    zhaquirks_const.DIM_UP: ha_const.TARGET_BUTTON_UP,
    zhaquirks_const.DIM_DOWN: ha_const.TARGET_BUTTON_DOWN,
    zhaquirks_const.ON: ha_const.TARGET_BUTTON_ON,
    zhaquirks_const.OFF: ha_const.TARGET_BUTTON_OFF,
    zhaquirks_const.LEFT: ha_const.TARGET_BUTTON_LEFT,
    zhaquirks_const.RIGHT: ha_const.TARGET_BUTTON_RIGHT,
    "both_buttons": ha_const.TARGET_BUTTON_ALL,
    "face_1": ha_const.TARGET_SIDE_1,
    "face_2": ha_const.TARGET_SIDE_2,
    "face_3": ha_const.TARGET_SIDE_3,
    "face_4": ha_const.TARGET_SIDE_4,
    "face_5": ha_const.TARGET_SIDE_5,
    "face_6": ha_const.TARGET_SIDE_6,
    "left": ha_const.TARGET_BUTTON_LEFT,
    "right": ha_const.TARGET_BUTTON_RIGHT,
    zhaquirks_const.SHAKEN: ha_const.TARGET_DEVICE,
    zhaquirks_const.SHORT_PRESS: ha_const.TARGET_DEVICE,
    zhaquirks_const.SHORT_RELEASE: ha_const.TARGET_DEVICE,
    zhaquirks_const.DOUBLE_PRESS: ha_const.TARGET_DEVICE,
    zhaquirks_const.TRIPLE_PRESS: ha_const.TARGET_DEVICE,
    zhaquirks_const.QUADRUPLE_PRESS: ha_const.TARGET_DEVICE,
    zhaquirks_const.QUINTUPLE_PRESS: ha_const.TARGET_DEVICE,
    zhaquirks_const.LONG_PRESS: ha_const.TARGET_DEVICE,
    zhaquirks_const.LONG_RELEASE: ha_const.TARGET_DEVICE,
    zhaquirks_const.COMMAND_TOGGLE: ha_const.TARGET_DEVICE,
    "device_tilted": ha_const.TARGET_DEVICE,
    "device_shaken": ha_const.TARGET_DEVICE,
}

INTERACTION_TYPES = {
    zhaquirks_const.ALT_DOUBLE_PRESS: ha_const.INTERACTION_TYPE_DOUBLE,
    zhaquirks_const.ALT_LONG_PRESS: ha_const.INTERACTION_TYPE_LONG_PRESS,
    zhaquirks_const.ALT_LONG_RELEASE: ha_const.INTERACTION_TYPE_LONG_RELEASE,
    zhaquirks_const.ALT_SHORT_PRESS: ha_const.INTERACTION_TYPE_SINGLE,
    zhaquirks_const.SHAKEN: ha_const.INTERACTION_TYPE_SHAKE,
    zhaquirks_const.SHORT_PRESS: ha_const.INTERACTION_TYPE_SINGLE,
    zhaquirks_const.SHORT_RELEASE: ha_const.INTERACTION_TYPE_RELEASE,
    zhaquirks_const.DOUBLE_PRESS: ha_const.INTERACTION_TYPE_DOUBLE,
    zhaquirks_const.TRIPLE_PRESS: ha_const.INTERACTION_TYPE_TRIPLE,
    zhaquirks_const.QUADRUPLE_PRESS: ha_const.INTERACTION_TYPE_QUADRUPLE,
    zhaquirks_const.QUINTUPLE_PRESS: ha_const.INTERACTION_TYPE_QUINTUPLE,
    zhaquirks_const.LONG_PRESS: ha_const.INTERACTION_TYPE_LONG_PRESS,
    zhaquirks_const.LONG_RELEASE: ha_const.INTERACTION_TYPE_LONG_RELEASE,
    zhaquirks_const.COMMAND_TOGGLE: ha_const.INTERACTION_TYPE_TOGGLE,
    "device_tilted": ha_const.INTERACTION_TYPE_TILT,
    "device_shaken": ha_const.INTERACTION_TYPE_SHAKE,
    "device_slid": ha_const.INTERACTION_TYPE_SLIDE,
    "device_dropped": ha_const.INTERACTION_TYPE_DROP,
    "device_rotated": ha_const.INTERACTION_TYPE_ROTATE,
    "device_knocked": ha_const.INTERACTION_TYPE_KNOCK,
    "device_flipped": ha_const.INTERACTION_TYPE_FLIP,
}


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

    @property
    def zigbee_signature(self) -> Dict[int, Dict[str, Any]]:
        """Get the zigbee signatures for the pools in channels."""
        return {
            signature[0]: signature[1]
            for signature in [pool.zigbee_signature for pool in self.pools]
        }

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
        triggers = self.zha_device.device_automation_triggers
        matched_trigger = None
        if triggers:
            for trigger_key, trigger in triggers.items():
                try:
                    trigger_schema = vol.Schema(
                        {vol.Required(key): value for key, value in trigger.items()},
                        extra=vol.ALLOW_EXTRA,
                    )
                    trigger_schema(event_data)
                    matched_trigger = trigger_key
                    break
                except vol.Invalid:
                    pass

        event_data_to_fire = {
            const.ATTR_DEVICE_IEEE: str(self.zha_device.ieee),
            const.ATTR_UNIQUE_ID: self.unique_id,
            ha_const.ATTR_DEVICE_ID: self.zha_device.device_id,
            **event_data,
        }

        if matched_trigger:
            event_data_to_fire[ha_const.INTERACTION_TYPE] = INTERACTION_TYPES.get(
                matched_trigger[0], matched_trigger[0]
            )
            event_data_to_fire[ha_const.INTERACTION_TARGET] = INTERACTION_TARGETS.get(
                matched_trigger[1], matched_trigger[1]
            )

        self.zha_device.hass.bus.async_fire(
            "zha_event",
            event_data_to_fire,
        )


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

    @property
    def zigbee_signature(self) -> Tuple[int, Dict[str, Any]]:
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
