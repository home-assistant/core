"""
Device for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import asyncio
from datetime import timedelta
from enum import Enum
import logging
import time

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from .channels import EventRelayChannel
from .const import (
    ATTR_ARGS,
    ATTR_ATTRIBUTE,
    ATTR_CLUSTER_ID,
    ATTR_COMMAND,
    ATTR_COMMAND_TYPE,
    ATTR_ENDPOINT_ID,
    ATTR_MANUFACTURER,
    ATTR_VALUE,
    BATTERY_OR_UNKNOWN,
    CLIENT_COMMANDS,
    IEEE,
    IN,
    MAINS_POWERED,
    MANUFACTURER_CODE,
    MODEL,
    NAME,
    NWK,
    OUT,
    POWER_CONFIGURATION_CHANNEL,
    POWER_SOURCE,
    QUIRK_APPLIED,
    QUIRK_CLASS,
    SERVER,
    SERVER_COMMANDS,
    SIGNAL_AVAILABLE,
    UNKNOWN_MANUFACTURER,
    UNKNOWN_MODEL,
    ZDO_CHANNEL,
    LQI,
    RSSI,
    LAST_SEEN,
    ATTR_AVAILABLE,
)
from .helpers import LogMixin

_LOGGER = logging.getLogger(__name__)
_KEEP_ALIVE_INTERVAL = 7200
_UPDATE_ALIVE_INTERVAL = timedelta(seconds=60)


class DeviceStatus(Enum):
    """Status of a device."""

    CREATED = 1
    INITIALIZED = 2


class ZHADevice(LogMixin):
    """ZHA Zigbee device object."""

    def __init__(self, hass, zigpy_device, zha_gateway):
        """Initialize the gateway."""
        self.hass = hass
        self._zigpy_device = zigpy_device
        self._zha_gateway = zha_gateway
        self.cluster_channels = {}
        self._relay_channels = {}
        self._all_channels = []
        self._available = False
        self._available_signal = "{}_{}_{}".format(
            self.name, self.ieee, SIGNAL_AVAILABLE
        )
        self._unsub = async_dispatcher_connect(
            self.hass, self._available_signal, self.async_initialize
        )
        from zigpy.quirks import CustomDevice

        self.quirk_applied = isinstance(self._zigpy_device, CustomDevice)
        self.quirk_class = "{}.{}".format(
            self._zigpy_device.__class__.__module__,
            self._zigpy_device.__class__.__name__,
        )
        self._available_check = async_track_time_interval(
            self.hass, self._check_available, _UPDATE_ALIVE_INTERVAL
        )
        self.status = DeviceStatus.CREATED

    @property
    def name(self):
        """Return device name."""
        return "{} {}".format(self.manufacturer, self.model)

    @property
    def ieee(self):
        """Return ieee address for device."""
        return self._zigpy_device.ieee

    @property
    def manufacturer(self):
        """Return manufacturer for device."""
        if self._zigpy_device.manufacturer is None:
            return UNKNOWN_MANUFACTURER
        return self._zigpy_device.manufacturer

    @property
    def model(self):
        """Return model for device."""
        if self._zigpy_device.model is None:
            return UNKNOWN_MODEL
        return self._zigpy_device.model

    @property
    def manufacturer_code(self):
        """Return the manufacturer code for the device."""
        if self._zigpy_device.node_desc.is_valid:
            return self._zigpy_device.node_desc.manufacturer_code
        return None

    @property
    def nwk(self):
        """Return nwk for device."""
        return self._zigpy_device.nwk

    @property
    def lqi(self):
        """Return lqi for device."""
        return self._zigpy_device.lqi

    @property
    def rssi(self):
        """Return rssi for device."""
        return self._zigpy_device.rssi

    @property
    def last_seen(self):
        """Return last_seen for device."""
        return self._zigpy_device.last_seen

    @property
    def is_mains_powered(self):
        """Return true if device is mains powered."""
        return self._zigpy_device.node_desc.is_mains_powered

    @property
    def power_source(self):
        """Return the power source for the device."""
        return MAINS_POWERED if self.is_mains_powered else BATTERY_OR_UNKNOWN

    @property
    def is_router(self):
        """Return true if this is a routing capable device."""
        return self._zigpy_device.node_desc.is_router

    @property
    def is_coordinator(self):
        """Return true if this device represents the coordinator."""
        return self._zigpy_device.node_desc.is_coordinator

    @property
    def is_end_device(self):
        """Return true if this device is an end device."""
        return self._zigpy_device.node_desc.is_end_device

    @property
    def gateway(self):
        """Return the gateway for this device."""
        return self._zha_gateway

    @property
    def all_channels(self):
        """Return cluster channels and relay channels for device."""
        return self._all_channels

    @property
    def available_signal(self):
        """Signal to use to subscribe to device availability changes."""
        return self._available_signal

    @property
    def available(self):
        """Return True if sensor is available."""
        return self._available

    def set_available(self, available):
        """Set availability from restore and prevent signals."""
        self._available = available

    def _check_available(self, *_):
        if self.last_seen is None:
            self.update_available(False)
        else:
            difference = time.time() - self.last_seen
            if difference > _KEEP_ALIVE_INTERVAL:
                self.update_available(False)
            else:
                self.update_available(True)

    def update_available(self, available):
        """Set sensor availability."""
        if self._available != available and available:
            # Update the state the first time the device comes online
            async_dispatcher_send(self.hass, self._available_signal, False)
        async_dispatcher_send(
            self.hass, "{}_{}".format(self._available_signal, "entity"), available
        )
        self._available = available

    @property
    def device_info(self):
        """Return a device description for device."""
        ieee = str(self.ieee)
        time_struct = time.localtime(self.last_seen)
        update_time = time.strftime("%Y-%m-%dT%H:%M:%S", time_struct)
        return {
            IEEE: ieee,
            NWK: self.nwk,
            ATTR_MANUFACTURER: self.manufacturer,
            MODEL: self.model,
            NAME: self.name or ieee,
            QUIRK_APPLIED: self.quirk_applied,
            QUIRK_CLASS: self.quirk_class,
            MANUFACTURER_CODE: self.manufacturer_code,
            POWER_SOURCE: self.power_source,
            LQI: self.lqi,
            RSSI: self.rssi,
            LAST_SEEN: update_time,
            ATTR_AVAILABLE: self.available,
        }

    def add_cluster_channel(self, cluster_channel):
        """Add cluster channel to device."""
        # only keep 1 power configuration channel
        if (
            cluster_channel.name is POWER_CONFIGURATION_CHANNEL
            and POWER_CONFIGURATION_CHANNEL in self.cluster_channels
        ):
            return

        if isinstance(cluster_channel, EventRelayChannel):
            self._relay_channels[cluster_channel.unique_id] = cluster_channel
            self._all_channels.append(cluster_channel)
        else:
            self.cluster_channels[cluster_channel.name] = cluster_channel
            self._all_channels.append(cluster_channel)

    def get_channels_to_configure(self):
        """Get a deduped list of channels for configuration.

        This goes through all channels and gets a unique list of channels to
        configure. It first assembles a unique list of channels that are part
        of entities while stashing relay channels off to the side. It then
        takse the stashed relay channels and adds them to the list of channels
        that will be returned if there isn't a channel in the list for that
        cluster already. This is done to ensure each cluster is only configured
        once.
        """
        channel_keys = []
        channels = []
        relay_channels = self._relay_channels.values()

        def get_key(channel):
            channel_key = "ZDO"
            if hasattr(channel.cluster, "cluster_id"):
                channel_key = "{}_{}".format(
                    channel.cluster.endpoint.endpoint_id, channel.cluster.cluster_id
                )
            return channel_key

        # first we get all unique non event channels
        for channel in self.all_channels:
            c_key = get_key(channel)
            if c_key not in channel_keys and channel not in relay_channels:
                channel_keys.append(c_key)
                channels.append(channel)

        # now we get event channels that still need their cluster configured
        for channel in relay_channels:
            channel_key = get_key(channel)
            if channel_key not in channel_keys:
                channel_keys.append(channel_key)
                channels.append(channel)
        return channels

    async def async_configure(self):
        """Configure the device."""
        self.debug("started configuration")
        await self._execute_channel_tasks(
            self.get_channels_to_configure(), "async_configure"
        )
        self.debug("completed configuration")
        entry = self.gateway.zha_storage.async_create_or_update(self)
        self.debug("stored in registry: %s", entry)

    async def async_initialize(self, from_cache=False):
        """Initialize channels."""
        self.debug("started initialization")
        await self._execute_channel_tasks(
            self.all_channels, "async_initialize", from_cache
        )
        self.debug("power source: %s", self.power_source)
        self.status = DeviceStatus.INITIALIZED
        self.debug("completed initialization")

    async def _execute_channel_tasks(self, channels, task_name, *args):
        """Gather and execute a set of CHANNEL tasks."""
        channel_tasks = []
        semaphore = asyncio.Semaphore(3)
        zdo_task = None
        for channel in channels:
            if channel.name == ZDO_CHANNEL:
                # pylint: disable=E1111
                if zdo_task is None:  # We only want to do this once
                    zdo_task = self._async_create_task(
                        semaphore, channel, task_name, *args
                    )
            else:
                channel_tasks.append(
                    self._async_create_task(semaphore, channel, task_name, *args)
                )
        if zdo_task is not None:
            await zdo_task
        await asyncio.gather(*channel_tasks)

    async def _async_create_task(self, semaphore, channel, func_name, *args):
        """Configure a single channel on this device."""
        try:
            async with semaphore:
                await getattr(channel, func_name)(*args)
                channel.debug("channel: '%s' stage succeeded", func_name)
        except Exception as ex:  # pylint: disable=broad-except
            channel.warning("channel: '%s' stage failed ex: %s", func_name, ex)

    @callback
    def async_unsub_dispatcher(self):
        """Unsubscribe the dispatcher."""
        if self._unsub:
            self._unsub()

    @callback
    def async_update_last_seen(self, last_seen):
        """Set last seen on the zigpy device."""
        self._zigpy_device.last_seen = last_seen

    @callback
    def async_get_clusters(self):
        """Get all clusters for this device."""
        return {
            ep_id: {IN: endpoint.in_clusters, OUT: endpoint.out_clusters}
            for (ep_id, endpoint) in self._zigpy_device.endpoints.items()
            if ep_id != 0
        }

    @callback
    def async_get_std_clusters(self):
        """Get ZHA and ZLL clusters for this device."""
        from zigpy.profiles import zha, zll

        return {
            ep_id: {IN: endpoint.in_clusters, OUT: endpoint.out_clusters}
            for (ep_id, endpoint) in self._zigpy_device.endpoints.items()
            if ep_id != 0 and endpoint.profile_id in (zha.PROFILE_ID, zll.PROFILE_ID)
        }

    @callback
    def async_get_cluster(self, endpoint_id, cluster_id, cluster_type=IN):
        """Get zigbee cluster from this entity."""
        clusters = self.async_get_clusters()
        return clusters[endpoint_id][cluster_type][cluster_id]

    @callback
    def async_get_cluster_attributes(self, endpoint_id, cluster_id, cluster_type=IN):
        """Get zigbee attributes for specified cluster."""
        cluster = self.async_get_cluster(endpoint_id, cluster_id, cluster_type)
        if cluster is None:
            return None
        return cluster.attributes

    @callback
    def async_get_cluster_commands(self, endpoint_id, cluster_id, cluster_type=IN):
        """Get zigbee commands for specified cluster."""
        cluster = self.async_get_cluster(endpoint_id, cluster_id, cluster_type)
        if cluster is None:
            return None
        return {
            CLIENT_COMMANDS: cluster.client_commands,
            SERVER_COMMANDS: cluster.server_commands,
        }

    async def write_zigbee_attribute(
        self,
        endpoint_id,
        cluster_id,
        attribute,
        value,
        cluster_type=IN,
        manufacturer=None,
    ):
        """Write a value to a zigbee attribute for a cluster in this entity."""
        cluster = self.async_get_cluster(endpoint_id, cluster_id, cluster_type)
        if cluster is None:
            return None

        from zigpy.exceptions import DeliveryError

        try:
            response = await cluster.write_attributes(
                {attribute: value}, manufacturer=manufacturer
            )
            self.debug(
                "set: %s for attr: %s to cluster: %s for ept: %s - res: %s",
                value,
                attribute,
                cluster_id,
                endpoint_id,
                response,
            )
            return response
        except DeliveryError as exc:
            self.debug(
                "failed to set attribute: %s %s %s %s %s",
                "{}: {}".format(ATTR_VALUE, value),
                "{}: {}".format(ATTR_ATTRIBUTE, attribute),
                "{}: {}".format(ATTR_CLUSTER_ID, cluster_id),
                "{}: {}".format(ATTR_ENDPOINT_ID, endpoint_id),
                exc,
            )
            return None

    async def issue_cluster_command(
        self,
        endpoint_id,
        cluster_id,
        command,
        command_type,
        args,
        cluster_type=IN,
        manufacturer=None,
    ):
        """Issue a command against specified zigbee cluster on this entity."""
        cluster = self.async_get_cluster(endpoint_id, cluster_id, cluster_type)
        if cluster is None:
            return None
        response = None
        if command_type == SERVER:
            response = await cluster.command(
                command, *args, manufacturer=manufacturer, expect_reply=True
            )
        else:
            response = await cluster.client_command(command, *args)

        self.debug(
            "Issued cluster command: %s %s %s %s %s %s %s",
            "{}: {}".format(ATTR_CLUSTER_ID, cluster_id),
            "{}: {}".format(ATTR_COMMAND, command),
            "{}: {}".format(ATTR_COMMAND_TYPE, command_type),
            "{}: {}".format(ATTR_ARGS, args),
            "{}: {}".format(ATTR_CLUSTER_ID, cluster_type),
            "{}: {}".format(ATTR_MANUFACTURER, manufacturer),
            "{}: {}".format(ATTR_ENDPOINT_ID, endpoint_id),
        )
        return response

    def log(self, level, msg, *args):
        """Log a message."""
        msg = "[%s](%s): " + msg
        args = (self.nwk, self.model) + args
        _LOGGER.log(level, msg, *args)
