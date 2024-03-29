"""Helper functions for the ZHA integration."""

import asyncio
import collections
from collections.abc import Callable
import dataclasses
import enum
import logging
import time
from typing import Any, NamedTuple

import voluptuous as vol
from zha.application.const import (
    ATTR_DEVICE_IEEE,
    ATTR_UNIQUE_ID,
    CLUSTER_TYPE_IN,
    CLUSTER_TYPE_OUT,
    DATA_ZHA,
    ZHA_EVENT,
)
from zha.application.gateway import Gateway
from zha.application.helpers import ZHAData
from zha.application.platforms import GroupEntity, PlatformEntity
from zha.event import EventBase
from zha.zigbee.cluster_handlers import ClusterHandler
from zha.zigbee.device import Device, ZHAEvent
import zigpy.exceptions
from zigpy.profiles import PROFILES
import zigpy.types
from zigpy.types import EUI64
import zigpy.util
import zigpy.zcl
from zigpy.zcl.foundation import CommandSchema

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    ATTR_ACTIVE_COORDINATOR,
    ATTR_AVAILABLE,
    ATTR_DEVICE_TYPE,
    ATTR_ENDPOINT_NAMES,
    ATTR_IEEE,
    ATTR_LAST_SEEN,
    ATTR_LQI,
    ATTR_MANUFACTURER,
    ATTR_MANUFACTURER_CODE,
    ATTR_MODEL,
    ATTR_NEIGHBORS,
    ATTR_NWK,
    ATTR_POWER_SOURCE,
    ATTR_QUIRK_APPLIED,
    ATTR_QUIRK_CLASS,
    ATTR_QUIRK_ID,
    ATTR_ROUTES,
    ATTR_RSSI,
    ATTR_SIGNATURE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ZHADeviceProxy(EventBase):
    """Proxy class to interact with the ZHA device instances."""

    def __init__(self, device: Device, gateway_proxy) -> None:
        """Initialize the gateway proxy."""
        super().__init__()
        self.device: Device = device
        self.gateway_proxy: ZHAGatewayProxy = gateway_proxy

        device_registry = dr.async_get(gateway_proxy.hass)
        self.ha_device_info: dr.DeviceEntry | None = device_registry.async_get_device(
            identifiers={(DOMAIN, str(device.ieee))},
            connections={(dr.CONNECTION_ZIGBEE, str(device.ieee))},
        )
        assert self.ha_device_info is not None
        self.device_id: str = self.ha_device_info.id

        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self.device.on_all_events(self._handle_event_protocol))

    @property
    def device_info(self) -> dict[str, Any]:
        """Return a device description for device."""
        ieee = str(self.device.ieee)
        time_struct = time.localtime(self.last_seen)
        update_time = time.strftime("%Y-%m-%dT%H:%M:%S", time_struct)
        return {
            ATTR_IEEE: ieee,
            ATTR_NWK: self.device.nwk,
            ATTR_MANUFACTURER: self.device.manufacturer,
            ATTR_MODEL: self.device.model,
            ATTR_NAME: self.device.name or ieee,
            ATTR_QUIRK_APPLIED: self.device.quirk_applied,
            ATTR_QUIRK_CLASS: self.device.quirk_class,
            ATTR_QUIRK_ID: self.device.quirk_id,
            ATTR_MANUFACTURER_CODE: self.device.manufacturer_code,
            ATTR_POWER_SOURCE: self.device.power_source,
            ATTR_LQI: self.device.lqi,
            ATTR_RSSI: self.device.rssi,
            ATTR_LAST_SEEN: update_time,
            ATTR_AVAILABLE: self.device.available,
            ATTR_DEVICE_TYPE: self.device.device_type,
            ATTR_SIGNATURE: self.device.zigbee_signature,
        }

    @property
    def zha_device_info(self) -> dict[str, Any]:
        """Get ZHA device information."""
        device_info: dict[str, Any] = {}
        device_info.update(self.device_info)
        device_info[ATTR_ACTIVE_COORDINATOR] = self.device.is_active_coordinator
        device_info["entities"] = [
            {
                "entity_id": entity_ref.reference_id,
                ATTR_NAME: entity_ref.device_info[ATTR_NAME],
            }
            for entity_ref in self.gateway_proxy.device_registry[self.device.ieee]
        ]

        topology = self.gateway_proxy.gateway.application_controller.topology
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
        for endpoint in (
            ep for epid, ep in self.device.device.endpoints.items() if epid
        ):
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

    def handle_zha_event(self, zha_event: ZHAEvent) -> None:
        """Handle a ZHA event."""
        if self.ha_device_info is not None:
            self.gateway_proxy.hass.bus.async_fire(
                ZHA_EVENT,
                {
                    ATTR_DEVICE_IEEE: zha_event.device_ieee,
                    ATTR_UNIQUE_ID: zha_event.unique_id,
                    ATTR_DEVICE_ID: self.ha_device_info.id,
                    **zha_event.data,
                },
            )


class EntityReference(NamedTuple):
    """Describes an entity reference."""

    reference_id: str
    zha_device: ZHADeviceProxy
    cluster_handlers: dict[str, ClusterHandler]
    device_info: dr.DeviceInfo
    remove_future: asyncio.Future[Any]


class ZHAGatewayProxy(EventBase):
    """Proxy class to interact with the ZHA gateway."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, gateway: Gateway
    ) -> None:
        """Initialize the gateway proxy."""
        super().__init__()
        self.hass = hass
        self.config_entry = config_entry
        self.gateway: Gateway = gateway
        self.device_proxies: dict[str, ZHADeviceProxy] = {}
        self._device_registry: collections.defaultdict[EUI64, list[EntityReference]] = (
            collections.defaultdict(list)
        )
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self.gateway.on_all_events(self._handle_event_protocol))

    @property
    def device_registry(self) -> collections.defaultdict[EUI64, list[EntityReference]]:
        """Return entities by ieee."""
        return self._device_registry

    def register_entity_reference(
        self,
        ieee: EUI64,
        reference_id: str,
        zha_device: ZHADeviceProxy,
        cluster_handlers: dict[str, ClusterHandler],
        device_info: dr.DeviceInfo,
        remove_future: asyncio.Future[Any],
    ):
        """Record the creation of a hass entity associated with ieee."""
        self._device_registry[ieee].append(
            EntityReference(
                reference_id=reference_id,
                zha_device=zha_device,
                cluster_handlers=cluster_handlers,
                device_info=device_info,
                remove_future=remove_future,
            )
        )

    async def async_initialize_devices_and_entities(self) -> None:
        """Initialize devices and entities."""
        ha_zha_data = get_zha_data(self.hass)
        for device in self.gateway.devices.values():
            device_proxy = ZHADeviceProxy(device, self)
            self.device_proxies[device.ieee] = device_proxy
            for entity in device.platform_entities.values():
                platform = Platform(entity.PLATFORM)
                ha_zha_data.platforms[platform].append(
                    EntityData(entity=entity, device_proxy=device_proxy)
                )
        for group in self.gateway.groups.values():
            for entity in group.group_entities.values():
                platform = Platform(entity.PLATFORM)
                ha_zha_data.platforms[platform].append(
                    EntityData(
                        entity=entity,
                        device_proxy=self.device_proxies[
                            self.gateway.coordinator_zha_device.ieee
                        ],
                    )
                )

        await self.gateway.async_initialize_devices_and_entities()

    async def shutdown(self) -> None:
        """Shutdown the gateway proxy."""
        for unsub in self._unsubs:
            unsub()
        await self.gateway.shutdown()


@dataclasses.dataclass(kw_only=True, slots=True)
class HAZHAData:
    """ZHA data stored in `hass.data`."""

    data: ZHAData
    gateway_proxy: ZHAGatewayProxy | None = dataclasses.field(default=None)
    platforms: collections.defaultdict[Platform, list] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(list)
    )
    update_coordinator: Any | None = dataclasses.field(default=None)


@dataclasses.dataclass(kw_only=True, slots=True)
class EntityData:
    """ZHA entity data."""

    entity: PlatformEntity | GroupEntity
    device_proxy: ZHADeviceProxy


def get_zha_data(hass: HomeAssistant) -> HAZHAData:
    """Get the global ZHA data object."""
    if DATA_ZHA not in hass.data:
        hass.data[DATA_ZHA] = HAZHAData(data=ZHAData())

    return hass.data[DATA_ZHA]


def get_zha_gateway(hass: HomeAssistant) -> Gateway:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists")

    return gateway_proxy.gateway


def get_zha_gateway_proxy(hass: HomeAssistant) -> ZHAGatewayProxy:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists")

    return gateway_proxy


def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists to retrieve the config entry from.")

    return gateway_proxy.config_entry


@callback
def async_get_zha_device_proxy(hass: HomeAssistant, device_id: str) -> ZHADeviceProxy:
    """Get a ZHA device for the given device registry id."""
    device_registry = dr.async_get(hass)
    registry_device = device_registry.async_get(device_id)
    if not registry_device:
        _LOGGER.error("Device id `%s` not found in registry", device_id)
        raise KeyError(f"Device id `{device_id}` not found in registry.")
    zha_gateway_proxy = get_zha_gateway_proxy(hass)
    try:
        ieee_address = list(registry_device.identifiers)[0][1]
        ieee = EUI64.convert(ieee_address)
    except (IndexError, ValueError) as ex:
        _LOGGER.error(
            "Unable to determine device IEEE for device with device id `%s`", device_id
        )
        raise KeyError(
            f"Unable to determine device IEEE for device with device id `{device_id}`."
        ) from ex
    return zha_gateway_proxy.device_proxies[ieee]


def cluster_command_schema_to_vol_schema(schema: CommandSchema) -> vol.Schema:
    """Convert a cluster command schema to a voluptuous schema."""
    return vol.Schema(
        {
            vol.Optional(field.name)
            if field.optional
            else vol.Required(field.name): schema_type_to_vol(field.type)
            for field in schema.fields
        }
    )


def schema_type_to_vol(field_type: Any) -> Any:
    """Convert a schema type to a voluptuous type."""
    if issubclass(field_type, enum.Flag) and field_type.__members__:
        return cv.multi_select(
            [key.replace("_", " ") for key in field_type.__members__]
        )
    if issubclass(field_type, enum.Enum) and field_type.__members__:
        return vol.In([key.replace("_", " ") for key in field_type.__members__])
    if (
        issubclass(field_type, zigpy.types.FixedIntType)
        or issubclass(field_type, enum.Flag)
        or issubclass(field_type, enum.Enum)
    ):
        return vol.All(
            vol.Coerce(int), vol.Range(field_type.min_value, field_type.max_value)
        )
    return str


def convert_to_zcl_values(
    fields: dict[str, Any], schema: CommandSchema
) -> dict[str, Any]:
    """Convert user input to ZCL values."""
    converted_fields: dict[str, Any] = {}
    for field in schema.fields:
        if field.name not in fields:
            continue
        value = fields[field.name]
        if issubclass(field.type, enum.Flag) and isinstance(value, list):
            new_value = 0

            for flag in value:
                if isinstance(flag, str):
                    new_value |= field.type[flag.replace(" ", "_")]
                else:
                    new_value |= flag

            value = field.type(new_value)
        elif issubclass(field.type, enum.Enum):
            value = (
                field.type[value.replace(" ", "_")]
                if isinstance(value, str)
                else field.type(value)
            )
        else:
            value = field.type(value)
        _LOGGER.debug(
            "Converted ZCL schema field(%s) value from: %s to: %s",
            field.name,
            fields[field.name],
            value,
        )
        converted_fields[field.name] = value
    return converted_fields


def async_cluster_exists(hass: HomeAssistant, cluster_id, skip_coordinator=True):
    """Determine if a device containing the specified in cluster is paired."""
    zha_gateway = get_zha_gateway(hass)
    zha_devices = zha_gateway.devices.values()
    for zha_device in zha_devices:
        if skip_coordinator and zha_device.is_coordinator:
            continue
        clusters_by_endpoint = zha_device.async_get_clusters()
        for clusters in clusters_by_endpoint.values():
            if (
                cluster_id in clusters[CLUSTER_TYPE_IN]
                or cluster_id in clusters[CLUSTER_TYPE_OUT]
            ):
                return True
    return False
