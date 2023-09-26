"""Device for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from enum import Enum
import logging
import random
import time
from typing import TYPE_CHECKING, Any, Self

from zigpy import types
import zigpy.device
import zigpy.exceptions
from zigpy.profiles import PROFILES
import zigpy.quirks
from zigpy.types.named import EUI64, NWK
from zigpy.zcl.clusters import Cluster
from zigpy.zcl.clusters.general import Groups, Identify
from zigpy.zcl.foundation import Status as ZclStatus, ZCLCommandDef
import zigpy.zdo.types as zdo_types

from homeassistant.backports.functools import cached_property
from homeassistant.const import ATTR_COMMAND, ATTR_DEVICE_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from . import const
from .cluster_handlers import ClusterHandler, ZDOClusterHandler
from .const import (
    ATTR_ACTIVE_COORDINATOR,
    ATTR_ARGS,
    ATTR_ATTRIBUTE,
    ATTR_AVAILABLE,
    ATTR_CLUSTER_ID,
    ATTR_CLUSTER_TYPE,
    ATTR_COMMAND_TYPE,
    ATTR_DEVICE_TYPE,
    ATTR_ENDPOINT_ID,
    ATTR_ENDPOINT_NAMES,
    ATTR_ENDPOINTS,
    ATTR_IEEE,
    ATTR_LAST_SEEN,
    ATTR_LQI,
    ATTR_MANUFACTURER,
    ATTR_MANUFACTURER_CODE,
    ATTR_MODEL,
    ATTR_NEIGHBORS,
    ATTR_NODE_DESCRIPTOR,
    ATTR_NWK,
    ATTR_PARAMS,
    ATTR_POWER_SOURCE,
    ATTR_QUIRK_APPLIED,
    ATTR_QUIRK_CLASS,
    ATTR_ROUTES,
    ATTR_RSSI,
    ATTR_SIGNATURE,
    ATTR_VALUE,
    CLUSTER_COMMAND_SERVER,
    CLUSTER_COMMANDS_CLIENT,
    CLUSTER_COMMANDS_SERVER,
    CLUSTER_TYPE_IN,
    CLUSTER_TYPE_OUT,
    CONF_CONSIDER_UNAVAILABLE_BATTERY,
    CONF_CONSIDER_UNAVAILABLE_MAINS,
    CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY,
    CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS,
    CONF_ENABLE_IDENTIFY_ON_JOIN,
    POWER_BATTERY_OR_UNKNOWN,
    POWER_MAINS_POWERED,
    SIGNAL_AVAILABLE,
    SIGNAL_UPDATE_DEVICE,
    UNKNOWN,
    UNKNOWN_MANUFACTURER,
    UNKNOWN_MODEL,
    ZHA_OPTIONS,
)
from .endpoint import Endpoint
from .helpers import LogMixin, async_get_zha_config_value, convert_to_zcl_values

if TYPE_CHECKING:
    from ..websocket_api import ClusterBinding
    from .gateway import ZHAGateway

_LOGGER = logging.getLogger(__name__)
_UPDATE_ALIVE_INTERVAL = (60, 90)
_CHECKIN_GRACE_PERIODS = 2


def get_device_automation_triggers(
    device: zigpy.device.Device,
) -> dict[tuple[str, str], dict[str, str]]:
    """Get the supported device automation triggers for a zigpy device."""
    return {
        ("device_offline", "device_offline"): {"device_event_type": "device_offline"},
        **getattr(device, "device_automation_triggers", {}),
    }


class DeviceStatus(Enum):
    """Status of a device."""

    CREATED = 1
    INITIALIZED = 2


class ZHADevice(LogMixin):
    """ZHA Zigbee device object."""

    _ha_device_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        zigpy_device: zigpy.device.Device,
        zha_gateway: ZHAGateway,
    ) -> None:
        """Initialize the gateway."""
        self.hass = hass
        self._zigpy_device = zigpy_device
        self._zha_gateway = zha_gateway
        self._available = False
        self._available_signal = f"{self.name}_{self.ieee}_{SIGNAL_AVAILABLE}"
        self._checkins_missed_count = 0
        self.unsubs: list[Callable[[], None]] = []
        self.quirk_applied = isinstance(self._zigpy_device, zigpy.quirks.CustomDevice)
        self.quirk_class = (
            f"{self._zigpy_device.__class__.__module__}."
            f"{self._zigpy_device.__class__.__name__}"
        )

        if self.is_mains_powered:
            self.consider_unavailable_time = async_get_zha_config_value(
                self._zha_gateway.config_entry,
                ZHA_OPTIONS,
                CONF_CONSIDER_UNAVAILABLE_MAINS,
                CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS,
            )
        else:
            self.consider_unavailable_time = async_get_zha_config_value(
                self._zha_gateway.config_entry,
                ZHA_OPTIONS,
                CONF_CONSIDER_UNAVAILABLE_BATTERY,
                CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY,
            )

        self._zdo_handler: ZDOClusterHandler = ZDOClusterHandler(self)
        self._power_config_ch: ClusterHandler | None = None
        self._identify_ch: ClusterHandler | None = None
        self._basic_ch: ClusterHandler | None = None
        self.status: DeviceStatus = DeviceStatus.CREATED

        self._endpoints: dict[int, Endpoint] = {}
        for ep_id, endpoint in zigpy_device.endpoints.items():
            if ep_id != 0:
                self._endpoints[ep_id] = Endpoint.new(endpoint, self)

        if not self.is_coordinator:
            keep_alive_interval = random.randint(*_UPDATE_ALIVE_INTERVAL)
            self.unsubs.append(
                async_track_time_interval(
                    self.hass,
                    self._check_available,
                    timedelta(seconds=keep_alive_interval),
                )
            )

    @property
    def device_id(self) -> str:
        """Return the HA device registry device id."""
        return self._ha_device_id

    def set_device_id(self, device_id: str) -> None:
        """Set the HA device registry device id."""
        self._ha_device_id = device_id

    @property
    def device(self) -> zigpy.device.Device:
        """Return underlying Zigpy device."""
        return self._zigpy_device

    @property
    def name(self) -> str:
        """Return device name."""
        return f"{self.manufacturer} {self.model}"

    @property
    def ieee(self) -> EUI64:
        """Return ieee address for device."""
        return self._zigpy_device.ieee

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device."""
        if self._zigpy_device.manufacturer is None:
            return UNKNOWN_MANUFACTURER
        return self._zigpy_device.manufacturer

    @property
    def model(self) -> str:
        """Return model for device."""
        if self._zigpy_device.model is None:
            return UNKNOWN_MODEL
        return self._zigpy_device.model

    @property
    def manufacturer_code(self) -> int | None:
        """Return the manufacturer code for the device."""
        if self._zigpy_device.node_desc is None:
            return None

        return self._zigpy_device.node_desc.manufacturer_code

    @property
    def nwk(self) -> NWK:
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
    def last_seen(self) -> float | None:
        """Return last_seen for device."""
        return self._zigpy_device.last_seen

    @property
    def is_mains_powered(self) -> bool | None:
        """Return true if device is mains powered."""
        if self._zigpy_device.node_desc is None:
            return None

        return self._zigpy_device.node_desc.is_mains_powered

    @property
    def device_type(self) -> str:
        """Return the logical device type for the device."""
        if self._zigpy_device.node_desc is None:
            return UNKNOWN

        return self._zigpy_device.node_desc.logical_type.name

    @property
    def power_source(self) -> str:
        """Return the power source for the device."""
        return (
            POWER_MAINS_POWERED if self.is_mains_powered else POWER_BATTERY_OR_UNKNOWN
        )

    @property
    def is_router(self) -> bool | None:
        """Return true if this is a routing capable device."""
        if self._zigpy_device.node_desc is None:
            return None

        return self._zigpy_device.node_desc.is_router

    @property
    def is_coordinator(self) -> bool | None:
        """Return true if this device represents a coordinator."""
        if self._zigpy_device.node_desc is None:
            return None

        return self._zigpy_device.node_desc.is_coordinator

    @property
    def is_active_coordinator(self) -> bool:
        """Return true if this device is the active coordinator."""
        if not self.is_coordinator:
            return False

        return self.ieee == self.gateway.coordinator_ieee

    @property
    def is_end_device(self) -> bool | None:
        """Return true if this device is an end device."""
        if self._zigpy_device.node_desc is None:
            return None

        return self._zigpy_device.node_desc.is_end_device

    @property
    def is_groupable(self) -> bool:
        """Return true if this device has a group cluster."""
        return self.is_coordinator or (
            self.available and bool(self.async_get_groupable_endpoints())
        )

    @property
    def skip_configuration(self) -> bool:
        """Return true if the device should not issue configuration related commands."""
        return self._zigpy_device.skip_configuration or bool(self.is_coordinator)

    @property
    def gateway(self):
        """Return the gateway for this device."""
        return self._zha_gateway

    @cached_property
    def device_automation_commands(self) -> dict[str, list[tuple[str, str]]]:
        """Return the a lookup of commands to etype/sub_type."""
        commands: dict[str, list[tuple[str, str]]] = {}
        for etype_subtype, trigger in self.device_automation_triggers.items():
            if command := trigger.get(ATTR_COMMAND):
                commands.setdefault(command, []).append(etype_subtype)
        return commands

    @cached_property
    def device_automation_triggers(self) -> dict[tuple[str, str], dict[str, str]]:
        """Return the device automation triggers for this device."""
        return get_device_automation_triggers(self._zigpy_device)

    @property
    def available_signal(self) -> str:
        """Signal to use to subscribe to device availability changes."""
        return self._available_signal

    @property
    def available(self):
        """Return True if device is available."""
        return self._available

    @available.setter
    def available(self, new_availability: bool) -> None:
        """Set device availability."""
        self._available = new_availability

    @property
    def power_configuration_ch(self) -> ClusterHandler | None:
        """Return power configuration cluster handler."""
        return self._power_config_ch

    @power_configuration_ch.setter
    def power_configuration_ch(self, cluster_handler: ClusterHandler) -> None:
        """Power configuration cluster handler setter."""
        if self._power_config_ch is None:
            self._power_config_ch = cluster_handler

    @property
    def basic_ch(self) -> ClusterHandler | None:
        """Return basic cluster handler."""
        return self._basic_ch

    @basic_ch.setter
    def basic_ch(self, cluster_handler: ClusterHandler) -> None:
        """Set the basic cluster handler."""
        if self._basic_ch is None:
            self._basic_ch = cluster_handler

    @property
    def identify_ch(self) -> ClusterHandler | None:
        """Return power configuration cluster handler."""
        return self._identify_ch

    @identify_ch.setter
    def identify_ch(self, cluster_handler: ClusterHandler) -> None:
        """Power configuration cluster handler setter."""
        if self._identify_ch is None:
            self._identify_ch = cluster_handler

    @property
    def zdo_cluster_handler(self) -> ZDOClusterHandler:
        """Return ZDO cluster handler."""
        return self._zdo_handler

    @property
    def endpoints(self) -> dict[int, Endpoint]:
        """Return the endpoints for this device."""
        return self._endpoints

    @property
    def zigbee_signature(self) -> dict[str, Any]:
        """Get zigbee signature for this device."""
        return {
            ATTR_NODE_DESCRIPTOR: str(self._zigpy_device.node_desc),
            ATTR_ENDPOINTS: {
                signature[0]: signature[1]
                for signature in [
                    endpoint.zigbee_signature for endpoint in self._endpoints.values()
                ]
            },
            ATTR_MANUFACTURER: self.manufacturer,
            ATTR_MODEL: self.model,
        }

    @classmethod
    def new(
        cls,
        hass: HomeAssistant,
        zigpy_dev: zigpy.device.Device,
        gateway: ZHAGateway,
        restored: bool = False,
    ) -> Self:
        """Create new device."""
        zha_dev = cls(hass, zigpy_dev, gateway)
        zha_dev.unsubs.append(
            async_dispatcher_connect(
                hass,
                SIGNAL_UPDATE_DEVICE.format(str(zha_dev.ieee)),
                zha_dev.async_update_sw_build_id,
            )
        )
        return zha_dev

    @callback
    def async_update_sw_build_id(self, sw_version: int) -> None:
        """Update device sw version."""
        if self.device_id is None:
            return

        device_registry = dr.async_get(self.hass)
        device_registry.async_update_device(
            self.device_id, sw_version=f"0x{sw_version:08x}"
        )

    async def _check_available(self, *_: Any) -> None:
        # don't flip the availability state of the coordinator
        if self.is_coordinator:
            return
        if self.last_seen is None:
            self.debug("last_seen is None, marking the device unavailable")
            self.update_available(False)
            return

        difference = time.time() - self.last_seen
        if difference < self.consider_unavailable_time:
            self.debug(
                "Device seen - marking the device available and resetting counter"
            )
            self.update_available(True)
            self._checkins_missed_count = 0
            return

        if (
            self._checkins_missed_count >= _CHECKIN_GRACE_PERIODS
            or self.manufacturer == "LUMI"
            or not self._endpoints
        ):
            self.debug(
                (
                    "last_seen is %s seconds ago and ping attempts have been exhausted,"
                    " marking the device unavailable"
                ),
                difference,
            )
            self.update_available(False)
            return

        self._checkins_missed_count += 1
        self.debug(
            "Attempting to checkin with device - missed checkins: %s",
            self._checkins_missed_count,
        )
        if not self.basic_ch:
            self.debug("does not have a mandatory basic cluster")
            self.update_available(False)
            return
        res = await self.basic_ch.get_attribute_value(
            ATTR_MANUFACTURER, from_cache=False
        )
        if res is not None:
            self._checkins_missed_count = 0

    def update_available(self, available: bool) -> None:
        """Update device availability and signal entities."""
        self.debug(
            (
                "Update device availability -  device available: %s - new availability:"
                " %s - changed: %s"
            ),
            self.available,
            available,
            self.available ^ available,
        )
        availability_changed = self.available ^ available
        self.available = available
        if availability_changed and available:
            # reinit cluster handlers then signal entities
            self.debug(
                "Device availability changed and device became available,"
                " reinitializing cluster handlers"
            )
            self.hass.async_create_task(self._async_became_available())
            return
        if availability_changed and not available:
            self.debug("Device availability changed and device became unavailable")
            self.zha_send_event(
                {
                    "device_event_type": "device_offline",
                },
            )
        async_dispatcher_send(self.hass, f"{self._available_signal}_entity")

    @callback
    def zha_send_event(self, event_data: dict[str, str | int]) -> None:
        """Relay events to hass."""
        self.hass.bus.async_fire(
            const.ZHA_EVENT,
            {
                const.ATTR_DEVICE_IEEE: str(self.ieee),
                const.ATTR_UNIQUE_ID: str(self.ieee),
                ATTR_DEVICE_ID: self.device_id,
                **event_data,
            },
        )

    async def _async_became_available(self) -> None:
        """Update device availability and signal entities."""
        await self.async_initialize(False)
        async_dispatcher_send(self.hass, f"{self._available_signal}_entity")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return a device description for device."""
        ieee = str(self.ieee)
        time_struct = time.localtime(self.last_seen)
        update_time = time.strftime("%Y-%m-%dT%H:%M:%S", time_struct)
        return {
            ATTR_IEEE: ieee,
            ATTR_NWK: self.nwk,
            ATTR_MANUFACTURER: self.manufacturer,
            ATTR_MODEL: self.model,
            ATTR_NAME: self.name or ieee,
            ATTR_QUIRK_APPLIED: self.quirk_applied,
            ATTR_QUIRK_CLASS: self.quirk_class,
            ATTR_MANUFACTURER_CODE: self.manufacturer_code,
            ATTR_POWER_SOURCE: self.power_source,
            ATTR_LQI: self.lqi,
            ATTR_RSSI: self.rssi,
            ATTR_LAST_SEEN: update_time,
            ATTR_AVAILABLE: self.available,
            ATTR_DEVICE_TYPE: self.device_type,
            ATTR_SIGNATURE: self.zigbee_signature,
        }

    async def async_configure(self) -> None:
        """Configure the device."""
        should_identify = async_get_zha_config_value(
            self._zha_gateway.config_entry,
            ZHA_OPTIONS,
            CONF_ENABLE_IDENTIFY_ON_JOIN,
            True,
        )
        self.debug("started configuration")
        await self._zdo_handler.async_configure()
        self._zdo_handler.debug("'async_configure' stage succeeded")
        await asyncio.gather(
            *(endpoint.async_configure() for endpoint in self._endpoints.values())
        )
        async_dispatcher_send(
            self.hass,
            const.ZHA_CLUSTER_HANDLER_MSG,
            {
                const.ATTR_TYPE: const.ZHA_CLUSTER_HANDLER_CFG_DONE,
            },
        )
        self.debug("completed configuration")

        if (
            should_identify
            and self.identify_ch is not None
            and not self.skip_configuration
        ):
            await self.identify_ch.trigger_effect(
                effect_id=Identify.EffectIdentifier.Okay,
                effect_variant=Identify.EffectVariant.Default,
            )

    async def async_initialize(self, from_cache: bool = False) -> None:
        """Initialize cluster handlers."""
        self.debug("started initialization")
        await self._zdo_handler.async_initialize(from_cache)
        self._zdo_handler.debug("'async_initialize' stage succeeded")
        await asyncio.gather(
            *(
                endpoint.async_initialize(from_cache)
                for endpoint in self._endpoints.values()
            )
        )
        self.debug("power source: %s", self.power_source)
        self.status = DeviceStatus.INITIALIZED
        self.debug("completed initialization")

    @callback
    def async_cleanup_handles(self) -> None:
        """Unsubscribe the dispatchers and timers."""
        for unsubscribe in self.unsubs:
            unsubscribe()

    @property
    def zha_device_info(self) -> dict[str, Any]:
        """Get ZHA device information."""
        device_info: dict[str, Any] = {}
        device_info.update(self.device_info)
        device_info[ATTR_ACTIVE_COORDINATOR] = self.is_active_coordinator
        device_info["entities"] = [
            {
                "entity_id": entity_ref.reference_id,
                ATTR_NAME: entity_ref.device_info[ATTR_NAME],
            }
            for entity_ref in self.gateway.device_registry[self.ieee]
        ]

        topology = self.gateway.application_controller.topology
        device_info[ATTR_NEIGHBORS] = [
            {
                "device_type": neighbor.device_type.name,
                "rx_on_when_idle": neighbor.rx_on_when_idle.name,
                "relationship": neighbor.relationship.name,
                "extended_pan_id": str(neighbor.extended_pan_id),
                "ieee": str(neighbor.ieee),
                "nwk": str(neighbor.nwk),
                "permit_joining": neighbor.permit_joining.name,
                "depth": str(neighbor.depth),
                "lqi": str(neighbor.lqi),
            }
            for neighbor in topology.neighbors[self.ieee]
        ]

        device_info[ATTR_ROUTES] = [
            {
                "dest_nwk": str(route.DstNWK),
                "route_status": str(route.RouteStatus.name),
                "memory_constrained": bool(route.MemoryConstrained),
                "many_to_one": bool(route.ManyToOne),
                "route_record_required": bool(route.RouteRecordRequired),
                "next_hop": str(route.NextHop),
            }
            for route in topology.routes[self.ieee]
        ]

        # Return endpoint device type Names
        names: list[dict[str, str]] = []
        for endpoint in (ep for epid, ep in self.device.endpoints.items() if epid):
            profile = PROFILES.get(endpoint.profile_id)
            if profile and endpoint.device_type is not None:
                # DeviceType provides undefined enums
                names.append({ATTR_NAME: profile.DeviceType(endpoint.device_type).name})
            else:
                names.append(
                    {
                        ATTR_NAME: (
                            f"unknown {endpoint.device_type} device_type "
                            f"of 0x{(endpoint.profile_id or 0xFFFF):04x} profile id"
                        )
                    }
                )
        device_info[ATTR_ENDPOINT_NAMES] = names

        device_registry = dr.async_get(self.hass)
        reg_device = device_registry.async_get(self.device_id)
        if reg_device is not None:
            device_info["user_given_name"] = reg_device.name_by_user
            device_info["device_reg_id"] = reg_device.id
            device_info["area_id"] = reg_device.area_id
        return device_info

    @callback
    def async_get_clusters(self) -> dict[int, dict[str, dict[int, Cluster]]]:
        """Get all clusters for this device."""
        return {
            ep_id: {
                CLUSTER_TYPE_IN: endpoint.in_clusters,
                CLUSTER_TYPE_OUT: endpoint.out_clusters,
            }
            for (ep_id, endpoint) in self._zigpy_device.endpoints.items()
            if ep_id != 0
        }

    @callback
    def async_get_groupable_endpoints(self):
        """Get device endpoints that have a group 'in' cluster."""
        return [
            ep_id
            for (ep_id, clusters) in self.async_get_clusters().items()
            if Groups.cluster_id in clusters[CLUSTER_TYPE_IN]
        ]

    @callback
    def async_get_std_clusters(self):
        """Get ZHA and ZLL clusters for this device."""

        return {
            ep_id: {
                CLUSTER_TYPE_IN: endpoint.in_clusters,
                CLUSTER_TYPE_OUT: endpoint.out_clusters,
            }
            for (ep_id, endpoint) in self._zigpy_device.endpoints.items()
            if ep_id != 0 and endpoint.profile_id in PROFILES
        }

    @callback
    def async_get_cluster(
        self, endpoint_id: int, cluster_id: int, cluster_type: str = CLUSTER_TYPE_IN
    ) -> Cluster:
        """Get zigbee cluster from this entity."""
        clusters: dict[int, dict[str, dict[int, Cluster]]] = self.async_get_clusters()
        return clusters[endpoint_id][cluster_type][cluster_id]

    @callback
    def async_get_cluster_attributes(
        self, endpoint_id, cluster_id, cluster_type=CLUSTER_TYPE_IN
    ):
        """Get zigbee attributes for specified cluster."""
        cluster = self.async_get_cluster(endpoint_id, cluster_id, cluster_type)
        if cluster is None:
            return None
        return cluster.attributes

    @callback
    def async_get_cluster_commands(
        self, endpoint_id, cluster_id, cluster_type=CLUSTER_TYPE_IN
    ):
        """Get zigbee commands for specified cluster."""
        cluster = self.async_get_cluster(endpoint_id, cluster_id, cluster_type)
        if cluster is None:
            return None
        return {
            CLUSTER_COMMANDS_CLIENT: cluster.client_commands,
            CLUSTER_COMMANDS_SERVER: cluster.server_commands,
        }

    async def write_zigbee_attribute(
        self,
        endpoint_id,
        cluster_id,
        attribute,
        value,
        cluster_type=CLUSTER_TYPE_IN,
        manufacturer=None,
    ):
        """Write a value to a zigbee attribute for a cluster in this entity."""
        try:
            cluster: Cluster = self.async_get_cluster(
                endpoint_id, cluster_id, cluster_type
            )
        except KeyError as exc:
            raise ValueError(
                f"Cluster {cluster_id} not found on endpoint {endpoint_id} while"
                f" writing attribute {attribute} with value {value}"
            ) from exc

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
        except zigpy.exceptions.ZigbeeException as exc:
            raise HomeAssistantError(
                f"Failed to set attribute: "
                f"{ATTR_VALUE}: {value} "
                f"{ATTR_ATTRIBUTE}: {attribute} "
                f"{ATTR_CLUSTER_ID}: {cluster_id} "
                f"{ATTR_ENDPOINT_ID}: {endpoint_id}"
            ) from exc

    async def issue_cluster_command(
        self,
        endpoint_id: int,
        cluster_id: int,
        command: int,
        command_type: str,
        args: list | None,
        params: dict[str, Any] | None,
        cluster_type: str = CLUSTER_TYPE_IN,
        manufacturer: int | None = None,
    ) -> None:
        """Issue a command against specified zigbee cluster on this device."""
        try:
            cluster: Cluster = self.async_get_cluster(
                endpoint_id, cluster_id, cluster_type
            )
        except KeyError as exc:
            raise ValueError(
                f"Cluster {cluster_id} not found on endpoint {endpoint_id} while"
                f" issuing command {command} with args {args}"
            ) from exc
        commands: dict[int, ZCLCommandDef] = (
            cluster.server_commands
            if command_type == CLUSTER_COMMAND_SERVER
            else cluster.client_commands
        )
        if args is not None:
            self.warning(
                (
                    "args [%s] are deprecated and should be passed with the params key."
                    " The parameter names are: %s"
                ),
                args,
                [field.name for field in commands[command].schema.fields],
            )
            response = await getattr(cluster, commands[command].name)(*args)
        else:
            assert params is not None
            response = await getattr(cluster, commands[command].name)(
                **convert_to_zcl_values(params, commands[command].schema)
            )
        self.debug(
            "Issued cluster command: %s %s %s %s %s %s %s %s",
            f"{ATTR_CLUSTER_ID}: [{cluster_id}]",
            f"{ATTR_CLUSTER_TYPE}: [{cluster_type}]",
            f"{ATTR_ENDPOINT_ID}: [{endpoint_id}]",
            f"{ATTR_COMMAND}: [{command}]",
            f"{ATTR_COMMAND_TYPE}: [{command_type}]",
            f"{ATTR_ARGS}: [{args}]",
            f"{ATTR_PARAMS}: [{params}]",
            f"{ATTR_MANUFACTURER}: [{manufacturer}]",
        )
        if response is None:
            return  # client commands don't return a response
        if isinstance(response, Exception):
            raise HomeAssistantError("Failed to issue cluster command") from response
        if response[1] is not ZclStatus.SUCCESS:
            raise HomeAssistantError(
                f"Failed to issue cluster command with status: {response[1]}"
            )

    async def async_add_to_group(self, group_id: int) -> None:
        """Add this device to the provided zigbee group."""
        try:
            # A group name is required. However, the spec also explicitly states that
            # the group name can be ignored by the receiving device if a device cannot
            # store it, so we cannot rely on it existing after being written. This is
            # only done to make the ZCL command valid.
            await self._zigpy_device.add_to_group(group_id, name=f"0x{group_id:04X}")
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                "Failed to add device '%s' to group: 0x%04x ex: %s",
                self._zigpy_device.ieee,
                group_id,
                str(ex),
            )

    async def async_remove_from_group(self, group_id: int) -> None:
        """Remove this device from the provided zigbee group."""
        try:
            await self._zigpy_device.remove_from_group(group_id)
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                "Failed to remove device '%s' from group: 0x%04x ex: %s",
                self._zigpy_device.ieee,
                group_id,
                str(ex),
            )

    async def async_add_endpoint_to_group(
        self, endpoint_id: int, group_id: int
    ) -> None:
        """Add the device endpoint to the provided zigbee group."""
        try:
            await self._zigpy_device.endpoints[endpoint_id].add_to_group(
                group_id, name=f"0x{group_id:04X}"
            )
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                "Failed to add endpoint: %s for device: '%s' to group: 0x%04x ex: %s",
                endpoint_id,
                self._zigpy_device.ieee,
                group_id,
                str(ex),
            )

    async def async_remove_endpoint_from_group(
        self, endpoint_id: int, group_id: int
    ) -> None:
        """Remove the device endpoint from the provided zigbee group."""
        try:
            await self._zigpy_device.endpoints[endpoint_id].remove_from_group(group_id)
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self.debug(
                (
                    "Failed to remove endpoint: %s for device '%s' from group: 0x%04x"
                    " ex: %s"
                ),
                endpoint_id,
                self._zigpy_device.ieee,
                group_id,
                str(ex),
            )

    async def async_bind_to_group(
        self, group_id: int, cluster_bindings: list[ClusterBinding]
    ) -> None:
        """Directly bind this device to a group for the given clusters."""
        await self._async_group_binding_operation(
            group_id, zdo_types.ZDOCmd.Bind_req, cluster_bindings
        )

    async def async_unbind_from_group(
        self, group_id: int, cluster_bindings: list[ClusterBinding]
    ) -> None:
        """Unbind this device from a group for the given clusters."""
        await self._async_group_binding_operation(
            group_id, zdo_types.ZDOCmd.Unbind_req, cluster_bindings
        )

    async def _async_group_binding_operation(
        self,
        group_id: int,
        operation: zdo_types.ZDOCmd,
        cluster_bindings: list[ClusterBinding],
    ) -> None:
        """Create or remove a direct zigbee binding between a device and a group."""

        zdo = self._zigpy_device.zdo
        op_msg = "0x%04x: %s %s, ep: %s, cluster: %s to group: 0x%04x"
        destination_address = zdo_types.MultiAddress()
        destination_address.addrmode = types.uint8_t(1)
        destination_address.nwk = types.uint16_t(group_id)

        tasks = []

        for cluster_binding in cluster_bindings:
            if cluster_binding.endpoint_id == 0:
                continue
            if (
                cluster_binding.id
                in self._zigpy_device.endpoints[
                    cluster_binding.endpoint_id
                ].out_clusters
            ):
                op_params = (
                    self.nwk,
                    operation.name,
                    str(self.ieee),
                    cluster_binding.endpoint_id,
                    cluster_binding.id,
                    group_id,
                )
                zdo.debug(f"processing {op_msg}", *op_params)
                tasks.append(
                    (
                        zdo.request(
                            operation,
                            self.ieee,
                            cluster_binding.endpoint_id,
                            cluster_binding.id,
                            destination_address,
                        ),
                        op_msg,
                        op_params,
                    )
                )
        res = await asyncio.gather(*(t[0] for t in tasks), return_exceptions=True)
        for outcome, log_msg in zip(res, tasks):
            if isinstance(outcome, Exception):
                fmt = f"{log_msg[1]} failed: %s"
            else:
                fmt = f"{log_msg[1]} completed: %s"
            zdo.debug(fmt, *(log_msg[2] + (outcome,)))

    def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (self.nwk, self.model) + args
        _LOGGER.log(level, msg, *args, **kwargs)
