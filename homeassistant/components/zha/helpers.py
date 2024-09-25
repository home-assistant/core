"""Helper functions for the ZHA integration."""

from __future__ import annotations

import asyncio
import collections
from collections.abc import Awaitable, Callable, Coroutine, Mapping
import copy
import dataclasses
import enum
import functools
import itertools
import logging
import re
import time
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Concatenate, NamedTuple, cast
from zoneinfo import ZoneInfo

import voluptuous as vol
from zha.application.const import (
    ATTR_CLUSTER_ID,
    ATTR_DEVICE_IEEE,
    ATTR_TYPE,
    ATTR_UNIQUE_ID,
    CLUSTER_TYPE_IN,
    CLUSTER_TYPE_OUT,
    CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY,
    CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS,
    UNKNOWN_MANUFACTURER,
    UNKNOWN_MODEL,
    ZHA_CLUSTER_HANDLER_CFG_DONE,
    ZHA_CLUSTER_HANDLER_MSG,
    ZHA_CLUSTER_HANDLER_MSG_BIND,
    ZHA_CLUSTER_HANDLER_MSG_CFG_RPT,
    ZHA_CLUSTER_HANDLER_MSG_DATA,
    ZHA_EVENT,
    ZHA_GW_MSG,
    ZHA_GW_MSG_DEVICE_FULL_INIT,
    ZHA_GW_MSG_DEVICE_INFO,
    ZHA_GW_MSG_DEVICE_JOINED,
    ZHA_GW_MSG_DEVICE_REMOVED,
    ZHA_GW_MSG_GROUP_ADDED,
    ZHA_GW_MSG_GROUP_INFO,
    ZHA_GW_MSG_GROUP_MEMBER_ADDED,
    ZHA_GW_MSG_GROUP_MEMBER_REMOVED,
    ZHA_GW_MSG_GROUP_REMOVED,
    ZHA_GW_MSG_RAW_INIT,
    RadioType,
)
from zha.application.gateway import (
    ConnectionLostEvent,
    DeviceFullInitEvent,
    DeviceJoinedEvent,
    DeviceLeftEvent,
    DeviceRemovedEvent,
    Gateway,
    GroupEvent,
    RawDeviceInitializedEvent,
)
from zha.application.helpers import (
    AlarmControlPanelOptions,
    CoordinatorConfiguration,
    DeviceOptions,
    DeviceOverridesConfiguration,
    LightOptions,
    QuirksConfiguration,
    ZHAConfiguration,
    ZHAData,
)
from zha.application.platforms import GroupEntity, PlatformEntity
from zha.event import EventBase
from zha.exceptions import ZHAException
from zha.mixins import LogMixin
from zha.zigbee.cluster_handlers import ClusterBindEvent, ClusterConfigureReportingEvent
from zha.zigbee.device import ClusterHandlerConfigurationComplete, Device, ZHAEvent
from zha.zigbee.group import Group, GroupInfo, GroupMember
from zigpy.config import (
    CONF_DATABASE,
    CONF_DEVICE,
    CONF_DEVICE_PATH,
    CONF_NWK,
    CONF_NWK_CHANNEL,
)
import zigpy.exceptions
from zigpy.profiles import PROFILES
import zigpy.types
from zigpy.types import EUI64
import zigpy.util
import zigpy.zcl
from zigpy.zcl.foundation import CommandSchema

from homeassistant import __path__ as HOMEASSISTANT_PATH
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
)
from homeassistant.components.system_log import LogEntry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_MODEL,
    ATTR_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ACTIVE_COORDINATOR,
    ATTR_ATTRIBUTES,
    ATTR_AVAILABLE,
    ATTR_CLUSTER_NAME,
    ATTR_DEVICE_TYPE,
    ATTR_ENDPOINT_NAMES,
    ATTR_IEEE,
    ATTR_LAST_SEEN,
    ATTR_LQI,
    ATTR_MANUFACTURER,
    ATTR_MANUFACTURER_CODE,
    ATTR_NEIGHBORS,
    ATTR_NWK,
    ATTR_POWER_SOURCE,
    ATTR_QUIRK_APPLIED,
    ATTR_QUIRK_CLASS,
    ATTR_QUIRK_ID,
    ATTR_ROUTES,
    ATTR_RSSI,
    ATTR_SIGNATURE,
    ATTR_SUCCESS,
    CONF_ALARM_ARM_REQUIRES_CODE,
    CONF_ALARM_FAILED_TRIES,
    CONF_ALARM_MASTER_CODE,
    CONF_BAUDRATE,
    CONF_CONSIDER_UNAVAILABLE_BATTERY,
    CONF_CONSIDER_UNAVAILABLE_MAINS,
    CONF_CUSTOM_QUIRKS_PATH,
    CONF_DEFAULT_LIGHT_TRANSITION,
    CONF_DEVICE_CONFIG,
    CONF_ENABLE_ENHANCED_LIGHT_TRANSITION,
    CONF_ENABLE_IDENTIFY_ON_JOIN,
    CONF_ENABLE_LIGHT_TRANSITIONING_FLAG,
    CONF_ENABLE_MAINS_STARTUP_POLLING,
    CONF_ENABLE_QUIRKS,
    CONF_FLOW_CONTROL,
    CONF_GROUP_MEMBERS_ASSUME_STATE,
    CONF_RADIO_TYPE,
    CONF_ZIGPY,
    CUSTOM_CONFIGURATION,
    DATA_ZHA,
    DEFAULT_DATABASE_NAME,
    DEVICE_PAIRING_STATUS,
    DOMAIN,
    ZHA_ALARM_OPTIONS,
    ZHA_OPTIONS,
)

if TYPE_CHECKING:
    from logging import Filter, LogRecord

    from .entity import ZHAEntity
    from .update import ZHAFirmwareUpdateCoordinator

    _LogFilterType = Filter | Callable[[LogRecord], bool]

_LOGGER = logging.getLogger(__name__)

DEBUG_COMP_BELLOWS = "bellows"
DEBUG_COMP_ZHA = "homeassistant.components.zha"
DEBUG_LIB_ZHA = "zha"
DEBUG_COMP_ZIGPY = "zigpy"
DEBUG_COMP_ZIGPY_ZNP = "zigpy_znp"
DEBUG_COMP_ZIGPY_DECONZ = "zigpy_deconz"
DEBUG_COMP_ZIGPY_XBEE = "zigpy_xbee"
DEBUG_COMP_ZIGPY_ZIGATE = "zigpy_zigate"
DEBUG_LEVEL_CURRENT = "current"
DEBUG_LEVEL_ORIGINAL = "original"
DEBUG_LEVELS = {
    DEBUG_COMP_BELLOWS: logging.DEBUG,
    DEBUG_COMP_ZHA: logging.DEBUG,
    DEBUG_COMP_ZIGPY: logging.DEBUG,
    DEBUG_COMP_ZIGPY_ZNP: logging.DEBUG,
    DEBUG_COMP_ZIGPY_DECONZ: logging.DEBUG,
    DEBUG_COMP_ZIGPY_XBEE: logging.DEBUG,
    DEBUG_COMP_ZIGPY_ZIGATE: logging.DEBUG,
    DEBUG_LIB_ZHA: logging.DEBUG,
}
DEBUG_RELAY_LOGGERS = [DEBUG_COMP_ZHA, DEBUG_COMP_ZIGPY, DEBUG_LIB_ZHA]
ZHA_GW_MSG_LOG_ENTRY = "log_entry"
ZHA_GW_MSG_LOG_OUTPUT = "log_output"
SIGNAL_REMOVE_ENTITIES = "zha_remove_entities"
GROUP_ENTITY_DOMAINS = [Platform.LIGHT, Platform.SWITCH, Platform.FAN]
SIGNAL_ADD_ENTITIES = "zha_add_entities"
ENTITIES = "entities"

RX_ON_WHEN_IDLE = "rx_on_when_idle"
RELATIONSHIP = "relationship"
EXTENDED_PAN_ID = "extended_pan_id"
PERMIT_JOINING = "permit_joining"
DEPTH = "depth"

DEST_NWK = "dest_nwk"
ROUTE_STATUS = "route_status"
MEMORY_CONSTRAINED = "memory_constrained"
MANY_TO_ONE = "many_to_one"
ROUTE_RECORD_REQUIRED = "route_record_required"
NEXT_HOP = "next_hop"

USER_GIVEN_NAME = "user_given_name"
DEVICE_REG_ID = "device_reg_id"


class GroupEntityReference(NamedTuple):
    """Reference to a group entity."""

    name: str | None
    original_name: str | None
    entity_id: str


class ZHAGroupProxy(LogMixin):
    """Proxy class to interact with the ZHA group instances."""

    def __init__(self, group: Group, gateway_proxy: ZHAGatewayProxy) -> None:
        """Initialize the gateway proxy."""
        self.group: Group = group
        self.gateway_proxy: ZHAGatewayProxy = gateway_proxy

    @property
    def group_info(self) -> dict[str, Any]:
        """Return a group description for group."""
        return {
            "name": self.group.name,
            "group_id": self.group.group_id,
            "members": [
                {
                    "endpoint_id": member.endpoint_id,
                    "device": self.gateway_proxy.device_proxies[
                        member.device.ieee
                    ].zha_device_info,
                    "entities": [e._asdict() for e in self.associated_entities(member)],
                }
                for member in self.group.members
            ],
        }

    def associated_entities(self, member: GroupMember) -> list[GroupEntityReference]:
        """Return the list of entities that were derived from this endpoint."""
        entity_registry = er.async_get(self.gateway_proxy.hass)
        entity_refs: collections.defaultdict[EUI64, list[EntityReference]] = (
            self.gateway_proxy.ha_entity_refs
        )

        entity_info = []

        for entity_ref in entity_refs.get(member.device.ieee):  # type: ignore[union-attr]
            if not entity_ref.entity_data.is_group_entity:
                continue
            entity = entity_registry.async_get(entity_ref.ha_entity_id)

            if (
                entity is None
                or entity_ref.entity_data.group_proxy is None
                or entity_ref.entity_data.group_proxy.group.group_id
                != member.group.group_id
            ):
                continue

            entity_info.append(
                GroupEntityReference(
                    name=entity.name,
                    original_name=entity.original_name,
                    entity_id=entity_ref.ha_entity_id,
                )
            )

        return entity_info

    def log(self, level: int, msg: str, *args: Any, **kwargs) -> None:
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (
            f"0x{self.group.group_id:04x}",
            self.group.endpoint.endpoint_id,
            *args,
        )
        _LOGGER.log(level, msg, *args, **kwargs)


class ZHADeviceProxy(EventBase):
    """Proxy class to interact with the ZHA device instances."""

    _ha_device_id: str

    def __init__(self, device: Device, gateway_proxy: ZHAGatewayProxy) -> None:
        """Initialize the gateway proxy."""
        super().__init__()
        self.device = device
        self.gateway_proxy = gateway_proxy
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self.device.on_all_events(self._handle_event_protocol))

    @property
    def device_id(self) -> str:
        """Return the HA device registry device id."""
        return self._ha_device_id

    @device_id.setter
    def device_id(self, device_id: str) -> None:
        """Set the HA device registry device id."""
        self._ha_device_id = device_id

    @property
    def device_info(self) -> dict[str, Any]:
        """Return a device description for device."""
        ieee = str(self.device.ieee)
        time_struct = time.localtime(self.device.last_seen)
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
        device_info[ENTITIES] = [
            {
                ATTR_ENTITY_ID: entity_ref.ha_entity_id,
                ATTR_NAME: entity_ref.ha_device_info[ATTR_NAME],
            }
            for entity_ref in self.gateway_proxy.ha_entity_refs[self.device.ieee]
        ]

        topology = self.gateway_proxy.gateway.application_controller.topology
        device_info[ATTR_NEIGHBORS] = [
            {
                ATTR_DEVICE_TYPE: neighbor.device_type.name,
                RX_ON_WHEN_IDLE: neighbor.rx_on_when_idle.name,
                RELATIONSHIP: neighbor.relationship.name,
                EXTENDED_PAN_ID: str(neighbor.extended_pan_id),
                ATTR_IEEE: str(neighbor.ieee),
                ATTR_NWK: str(neighbor.nwk),
                PERMIT_JOINING: neighbor.permit_joining.name,
                DEPTH: str(neighbor.depth),
                ATTR_LQI: str(neighbor.lqi),
            }
            for neighbor in topology.neighbors[self.device.ieee]
        ]

        device_info[ATTR_ROUTES] = [
            {
                DEST_NWK: str(route.DstNWK),
                ROUTE_STATUS: str(route.RouteStatus.name),
                MEMORY_CONSTRAINED: bool(route.MemoryConstrained),
                MANY_TO_ONE: bool(route.ManyToOne),
                ROUTE_RECORD_REQUIRED: bool(route.RouteRecordRequired),
                NEXT_HOP: str(route.NextHop),
            }
            for route in topology.routes[self.device.ieee]
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

        device_registry = dr.async_get(self.gateway_proxy.hass)
        reg_device = device_registry.async_get(self.device_id)
        if reg_device is not None:
            device_info[USER_GIVEN_NAME] = reg_device.name_by_user
            device_info[DEVICE_REG_ID] = reg_device.id
            device_info[ATTR_AREA_ID] = reg_device.area_id
        return device_info

    @callback
    def handle_zha_event(self, zha_event: ZHAEvent) -> None:
        """Handle a ZHA event."""
        self.gateway_proxy.hass.bus.async_fire(
            ZHA_EVENT,
            {
                ATTR_DEVICE_IEEE: str(zha_event.device_ieee),
                ATTR_UNIQUE_ID: zha_event.unique_id,
                ATTR_DEVICE_ID: self.device_id,
                **zha_event.data,
            },
        )

    @callback
    def handle_zha_channel_configure_reporting(
        self, event: ClusterConfigureReportingEvent
    ) -> None:
        """Handle a ZHA cluster configure reporting event."""
        async_dispatcher_send(
            self.gateway_proxy.hass,
            ZHA_CLUSTER_HANDLER_MSG,
            {
                ATTR_TYPE: ZHA_CLUSTER_HANDLER_MSG_CFG_RPT,
                ZHA_CLUSTER_HANDLER_MSG_DATA: {
                    ATTR_CLUSTER_NAME: event.cluster_name,
                    ATTR_CLUSTER_ID: event.cluster_id,
                    ATTR_ATTRIBUTES: event.attributes,
                },
            },
        )

    @callback
    def handle_zha_channel_cfg_done(
        self, event: ClusterHandlerConfigurationComplete
    ) -> None:
        """Handle a ZHA cluster configure reporting event."""
        async_dispatcher_send(
            self.gateway_proxy.hass,
            ZHA_CLUSTER_HANDLER_MSG,
            {
                ATTR_TYPE: ZHA_CLUSTER_HANDLER_CFG_DONE,
            },
        )

    @callback
    def handle_zha_channel_bind(self, event: ClusterBindEvent) -> None:
        """Handle a ZHA cluster bind event."""
        async_dispatcher_send(
            self.gateway_proxy.hass,
            ZHA_CLUSTER_HANDLER_MSG,
            {
                ATTR_TYPE: ZHA_CLUSTER_HANDLER_MSG_BIND,
                ZHA_CLUSTER_HANDLER_MSG_DATA: {
                    ATTR_CLUSTER_NAME: event.cluster_name,
                    ATTR_CLUSTER_ID: event.cluster_id,
                    ATTR_SUCCESS: event.success,
                },
            },
        )


class EntityReference(NamedTuple):
    """Describes an entity reference."""

    ha_entity_id: str
    entity_data: EntityData
    ha_device_info: dr.DeviceInfo
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
        self.gateway = gateway
        self.device_proxies: dict[str, ZHADeviceProxy] = {}
        self.group_proxies: dict[int, ZHAGroupProxy] = {}
        self._ha_entity_refs: collections.defaultdict[EUI64, list[EntityReference]] = (
            collections.defaultdict(list)
        )
        self._log_levels: dict[str, dict[str, int]] = {
            DEBUG_LEVEL_ORIGINAL: async_capture_log_levels(),
            DEBUG_LEVEL_CURRENT: async_capture_log_levels(),
        }
        self.debug_enabled: bool = False
        self._log_relay_handler: LogRelayHandler = LogRelayHandler(hass, self)
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self.gateway.on_all_events(self._handle_event_protocol))
        self._reload_task: asyncio.Task | None = None

    @property
    def ha_entity_refs(self) -> collections.defaultdict[EUI64, list[EntityReference]]:
        """Return entities by ieee."""
        return self._ha_entity_refs

    def register_entity_reference(
        self,
        ha_entity_id: str,
        entity_data: EntityData,
        ha_device_info: dr.DeviceInfo,
        remove_future: asyncio.Future[Any],
    ) -> None:
        """Record the creation of a hass entity associated with ieee."""
        self._ha_entity_refs[entity_data.device_proxy.device.ieee].append(
            EntityReference(
                ha_entity_id=ha_entity_id,
                entity_data=entity_data,
                ha_device_info=ha_device_info,
                remove_future=remove_future,
            )
        )

    async def async_initialize_devices_and_entities(self) -> None:
        """Initialize devices and entities."""
        for device in self.gateway.devices.values():
            device_proxy = self._async_get_or_create_device_proxy(device)
            self._create_entity_metadata(device_proxy)
        for group in self.gateway.groups.values():
            group_proxy = self._async_get_or_create_group_proxy(group)
            self._create_entity_metadata(group_proxy)

        await self.gateway.async_initialize_devices_and_entities()

    @callback
    def handle_connection_lost(self, event: ConnectionLostEvent) -> None:
        """Handle a connection lost event."""

        _LOGGER.debug("Connection to the radio was lost: %r", event)

        # Ensure we do not queue up multiple resets
        if self._reload_task is not None:
            _LOGGER.debug("Ignoring reset, one is already running")
            return

        self._reload_task = self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id),
        )

    @callback
    def handle_device_joined(self, event: DeviceJoinedEvent) -> None:
        """Handle a device joined event."""
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_JOINED,
                ZHA_GW_MSG_DEVICE_INFO: {
                    ATTR_NWK: event.device_info.nwk,
                    ATTR_IEEE: str(event.device_info.ieee),
                    DEVICE_PAIRING_STATUS: event.device_info.pairing_status.name,
                },
            },
        )

    @callback
    def handle_device_removed(self, event: DeviceRemovedEvent) -> None:
        """Handle a device removed event."""
        zha_device_proxy = self.device_proxies.pop(event.device_info.ieee, None)
        entity_refs = self._ha_entity_refs.pop(event.device_info.ieee, None)
        if zha_device_proxy is not None:
            device_info = zha_device_proxy.zha_device_info
            # zha_device_proxy.async_cleanup_handles()
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_REMOVE_ENTITIES}_{zha_device_proxy.device.ieee!s}",
            )
            self.hass.async_create_task(
                self._async_remove_device(zha_device_proxy, entity_refs),
                "ZHAGateway._async_remove_device",
            )
            if device_info is not None:
                async_dispatcher_send(
                    self.hass,
                    ZHA_GW_MSG,
                    {
                        ATTR_TYPE: ZHA_GW_MSG_DEVICE_REMOVED,
                        ZHA_GW_MSG_DEVICE_INFO: device_info,
                    },
                )

    @callback
    def handle_device_left(self, event: DeviceLeftEvent) -> None:
        """Handle a device left event."""

    @callback
    def handle_raw_device_initialized(self, event: RawDeviceInitializedEvent) -> None:
        """Handle a raw device initialized event."""
        manuf = event.device_info.manufacturer
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_RAW_INIT,
                ZHA_GW_MSG_DEVICE_INFO: {
                    ATTR_NWK: str(event.device_info.nwk),
                    ATTR_IEEE: str(event.device_info.ieee),
                    DEVICE_PAIRING_STATUS: event.device_info.pairing_status.name,
                    ATTR_MODEL: (
                        event.device_info.model
                        if event.device_info.model
                        else UNKNOWN_MODEL
                    ),
                    ATTR_MANUFACTURER: manuf if manuf else UNKNOWN_MANUFACTURER,
                    ATTR_SIGNATURE: event.device_info.signature,
                },
            },
        )

    @callback
    def handle_device_fully_initialized(self, event: DeviceFullInitEvent) -> None:
        """Handle a device fully initialized event."""
        zha_device = self.gateway.get_device(event.device_info.ieee)
        zha_device_proxy = self._async_get_or_create_device_proxy(zha_device)

        device_info = zha_device_proxy.zha_device_info
        device_info[DEVICE_PAIRING_STATUS] = event.device_info.pairing_status.name
        if event.new_join:
            self._create_entity_metadata(zha_device_proxy)
            async_dispatcher_send(self.hass, SIGNAL_ADD_ENTITIES)
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_FULL_INIT,
                ZHA_GW_MSG_DEVICE_INFO: device_info,
            },
        )

    @callback
    def handle_group_member_removed(self, event: GroupEvent) -> None:
        """Handle a group member removed event."""
        zha_group_proxy = self._async_get_or_create_group_proxy(event.group_info)
        zha_group_proxy.info("group_member_removed - group_info: %s", event.group_info)
        self._update_group_entities(event)
        self._send_group_gateway_message(
            zha_group_proxy, ZHA_GW_MSG_GROUP_MEMBER_REMOVED
        )

    @callback
    def handle_group_member_added(self, event: GroupEvent) -> None:
        """Handle a group member added event."""
        zha_group_proxy = self._async_get_or_create_group_proxy(event.group_info)
        zha_group_proxy.info("group_member_added - group_info: %s", event.group_info)
        self._send_group_gateway_message(zha_group_proxy, ZHA_GW_MSG_GROUP_MEMBER_ADDED)
        self._update_group_entities(event)

    @callback
    def handle_group_added(self, event: GroupEvent) -> None:
        """Handle a group added event."""
        zha_group_proxy = self._async_get_or_create_group_proxy(event.group_info)
        zha_group_proxy.info("group_added")
        self._update_group_entities(event)
        self._send_group_gateway_message(zha_group_proxy, ZHA_GW_MSG_GROUP_ADDED)

    @callback
    def handle_group_removed(self, event: GroupEvent) -> None:
        """Handle a group removed event."""
        zha_group_proxy = self.group_proxies.pop(event.group_info.group_id)
        self._send_group_gateway_message(zha_group_proxy, ZHA_GW_MSG_GROUP_REMOVED)
        zha_group_proxy.info("group_removed")
        self._cleanup_group_entity_registry_entries(zha_group_proxy)

    @callback
    def async_enable_debug_mode(self, filterer: _LogFilterType | None = None) -> None:
        """Enable debug mode for ZHA."""
        self._log_levels[DEBUG_LEVEL_ORIGINAL] = async_capture_log_levels()
        async_set_logger_levels(DEBUG_LEVELS)
        self._log_levels[DEBUG_LEVEL_CURRENT] = async_capture_log_levels()

        if filterer:
            self._log_relay_handler.addFilter(filterer)

        for logger_name in DEBUG_RELAY_LOGGERS:
            logging.getLogger(logger_name).addHandler(self._log_relay_handler)

        self.debug_enabled = True

    @callback
    def async_disable_debug_mode(self, filterer: _LogFilterType | None = None) -> None:
        """Disable debug mode for ZHA."""
        async_set_logger_levels(self._log_levels[DEBUG_LEVEL_ORIGINAL])
        self._log_levels[DEBUG_LEVEL_CURRENT] = async_capture_log_levels()
        for logger_name in DEBUG_RELAY_LOGGERS:
            logging.getLogger(logger_name).removeHandler(self._log_relay_handler)
        if filterer:
            self._log_relay_handler.removeFilter(filterer)
        self.debug_enabled = False

    async def shutdown(self) -> None:
        """Shutdown the gateway proxy."""
        for unsub in self._unsubs:
            unsub()
        await self.gateway.shutdown()

    def get_device_proxy(self, ieee: EUI64) -> ZHADeviceProxy | None:
        """Return ZHADevice for given ieee."""
        return self.device_proxies.get(ieee)

    def get_group_proxy(self, group_id: int | str) -> ZHAGroupProxy | None:
        """Return Group for given group id."""
        if isinstance(group_id, str):
            for group_proxy in self.group_proxies.values():
                if group_proxy.group.name == group_id:
                    return group_proxy
            return None
        return self.group_proxies.get(group_id)

    def get_entity_reference(self, entity_id: str) -> EntityReference | None:
        """Return entity reference for given entity_id if found."""
        for entity_reference in itertools.chain.from_iterable(
            self.ha_entity_refs.values()
        ):
            if entity_id == entity_reference.ha_entity_id:
                return entity_reference
        return None

    def remove_entity_reference(self, entity: ZHAEntity) -> None:
        """Remove entity reference for given entity_id if found."""
        if entity.zha_device.ieee in self.ha_entity_refs:
            entity_refs = self.ha_entity_refs.get(entity.zha_device.ieee)
            self.ha_entity_refs[entity.zha_device.ieee] = [
                e
                for e in entity_refs  # type: ignore[union-attr]
                if e.ha_entity_id != entity.entity_id
            ]

    def _async_get_or_create_device_proxy(self, zha_device: Device) -> ZHADeviceProxy:
        """Get or create a ZHA device."""
        if (zha_device_proxy := self.device_proxies.get(zha_device.ieee)) is None:
            zha_device_proxy = ZHADeviceProxy(zha_device, self)
            self.device_proxies[zha_device_proxy.device.ieee] = zha_device_proxy

            device_registry = dr.async_get(self.hass)
            device_registry_device = device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                connections={(dr.CONNECTION_ZIGBEE, str(zha_device.ieee))},
                identifiers={(DOMAIN, str(zha_device.ieee))},
                name=zha_device.name,
                manufacturer=zha_device.manufacturer,
                model=zha_device.model,
            )
            zha_device_proxy.device_id = device_registry_device.id
        return zha_device_proxy

    def _async_get_or_create_group_proxy(self, group_info: GroupInfo) -> ZHAGroupProxy:
        """Get or create a ZHA group."""
        zha_group_proxy = self.group_proxies.get(group_info.group_id)
        if zha_group_proxy is None:
            zha_group_proxy = ZHAGroupProxy(
                self.gateway.groups[group_info.group_id], self
            )
            self.group_proxies[group_info.group_id] = zha_group_proxy
        return zha_group_proxy

    def _create_entity_metadata(
        self, proxy_object: ZHADeviceProxy | ZHAGroupProxy
    ) -> None:
        """Create HA entity metadata."""
        ha_zha_data = get_zha_data(self.hass)
        coordinator_proxy = self.device_proxies[
            self.gateway.coordinator_zha_device.ieee
        ]

        if isinstance(proxy_object, ZHADeviceProxy):
            for entity in proxy_object.device.platform_entities.values():
                ha_zha_data.platforms[Platform(entity.PLATFORM)].append(
                    EntityData(
                        entity=entity, device_proxy=proxy_object, group_proxy=None
                    )
                )
        else:
            for entity in proxy_object.group.group_entities.values():
                ha_zha_data.platforms[Platform(entity.PLATFORM)].append(
                    EntityData(
                        entity=entity,
                        device_proxy=coordinator_proxy,
                        group_proxy=proxy_object,
                    )
                )

    def _cleanup_group_entity_registry_entries(
        self, zha_group_proxy: ZHAGroupProxy
    ) -> None:
        """Remove entity registry entries for group entities when the groups are removed from HA."""
        # first we collect the potential unique ids for entities that could be created from this group
        possible_entity_unique_ids = [
            f"{domain}_zha_group_0x{zha_group_proxy.group.group_id:04x}"
            for domain in GROUP_ENTITY_DOMAINS
        ]

        # then we get all group entity entries tied to the coordinator
        entity_registry = er.async_get(self.hass)
        assert self.gateway.coordinator_zha_device
        coordinator_proxy = self.device_proxies[
            self.gateway.coordinator_zha_device.ieee
        ]
        all_group_entity_entries = er.async_entries_for_device(
            entity_registry,
            coordinator_proxy.device_id,
            include_disabled_entities=True,
        )

        # then we get the entity entries for this specific group
        # by getting the entries that match
        entries_to_remove = [
            entry
            for entry in all_group_entity_entries
            if entry.unique_id in possible_entity_unique_ids
        ]

        # then we remove the entries from the entity registry
        for entry in entries_to_remove:
            _LOGGER.debug(
                "cleaning up entity registry entry for entity: %s", entry.entity_id
            )
            entity_registry.async_remove(entry.entity_id)

    def _update_group_entities(self, group_event: GroupEvent) -> None:
        """Update group entities when a group event is received."""
        async_dispatcher_send(
            self.hass,
            f"{SIGNAL_REMOVE_ENTITIES}_group_{group_event.group_info.group_id}",
        )
        self._create_entity_metadata(
            self.group_proxies[group_event.group_info.group_id]
        )
        async_dispatcher_send(self.hass, SIGNAL_ADD_ENTITIES)

    def _send_group_gateway_message(
        self, zha_group_proxy: ZHAGroupProxy, gateway_message_type: str
    ) -> None:
        """Send the gateway event for a zigpy group event."""
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: gateway_message_type,
                ZHA_GW_MSG_GROUP_INFO: zha_group_proxy.group_info,
            },
        )

    async def _async_remove_device(
        self, device: ZHADeviceProxy, entity_refs: list[EntityReference] | None
    ) -> None:
        if entity_refs is not None:
            remove_tasks: list[asyncio.Future[Any]] = [
                entity_ref.remove_future for entity_ref in entity_refs
            ]
            if remove_tasks:
                await asyncio.wait(remove_tasks)

        device_registry = dr.async_get(self.hass)
        reg_device = device_registry.async_get(device.device_id)
        if reg_device is not None:
            device_registry.async_remove_device(reg_device.id)


@callback
def async_capture_log_levels() -> dict[str, int]:
    """Capture current logger levels for ZHA."""
    return {
        DEBUG_COMP_BELLOWS: logging.getLogger(DEBUG_COMP_BELLOWS).getEffectiveLevel(),
        DEBUG_COMP_ZHA: logging.getLogger(DEBUG_COMP_ZHA).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY: logging.getLogger(DEBUG_COMP_ZIGPY).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_ZNP: logging.getLogger(
            DEBUG_COMP_ZIGPY_ZNP
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_DECONZ: logging.getLogger(
            DEBUG_COMP_ZIGPY_DECONZ
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_XBEE: logging.getLogger(
            DEBUG_COMP_ZIGPY_XBEE
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_ZIGATE: logging.getLogger(
            DEBUG_COMP_ZIGPY_ZIGATE
        ).getEffectiveLevel(),
        DEBUG_LIB_ZHA: logging.getLogger(DEBUG_LIB_ZHA).getEffectiveLevel(),
    }


@callback
def async_set_logger_levels(levels: dict[str, int]) -> None:
    """Set logger levels for ZHA."""
    logging.getLogger(DEBUG_COMP_BELLOWS).setLevel(levels[DEBUG_COMP_BELLOWS])
    logging.getLogger(DEBUG_COMP_ZHA).setLevel(levels[DEBUG_COMP_ZHA])
    logging.getLogger(DEBUG_COMP_ZIGPY).setLevel(levels[DEBUG_COMP_ZIGPY])
    logging.getLogger(DEBUG_COMP_ZIGPY_ZNP).setLevel(levels[DEBUG_COMP_ZIGPY_ZNP])
    logging.getLogger(DEBUG_COMP_ZIGPY_DECONZ).setLevel(levels[DEBUG_COMP_ZIGPY_DECONZ])
    logging.getLogger(DEBUG_COMP_ZIGPY_XBEE).setLevel(levels[DEBUG_COMP_ZIGPY_XBEE])
    logging.getLogger(DEBUG_COMP_ZIGPY_ZIGATE).setLevel(levels[DEBUG_COMP_ZIGPY_ZIGATE])
    logging.getLogger(DEBUG_LIB_ZHA).setLevel(levels[DEBUG_LIB_ZHA])


class LogRelayHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(self, hass: HomeAssistant, gateway: ZHAGatewayProxy) -> None:
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.hass = hass
        self.gateway = gateway
        hass_path: str = HOMEASSISTANT_PATH[0]
        config_dir = self.hass.config.config_dir
        self.paths_re = re.compile(
            rf"(?:{re.escape(hass_path)}|{re.escape(config_dir)})/(.*)"
        )

    def emit(self, record: LogRecord) -> None:
        """Relay log message via dispatcher."""
        entry = LogEntry(
            record, self.paths_re, figure_out_source=record.levelno >= logging.WARNING
        )
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {ATTR_TYPE: ZHA_GW_MSG_LOG_OUTPUT, ZHA_GW_MSG_LOG_ENTRY: entry.to_dict()},
        )


@dataclasses.dataclass(kw_only=True, slots=True)
class HAZHAData:
    """ZHA data stored in `hass.data`."""

    yaml_config: ConfigType = dataclasses.field(default_factory=dict)
    config_entry: ConfigEntry | None = dataclasses.field(default=None)
    device_trigger_cache: dict[str, tuple[str, dict]] = dataclasses.field(
        default_factory=dict
    )
    gateway_proxy: ZHAGatewayProxy | None = dataclasses.field(default=None)
    platforms: collections.defaultdict[Platform, list] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(list)
    )
    update_coordinator: ZHAFirmwareUpdateCoordinator | None = dataclasses.field(
        default=None
    )


@dataclasses.dataclass(kw_only=True, slots=True)
class EntityData:
    """ZHA entity data."""

    entity: PlatformEntity | GroupEntity
    device_proxy: ZHADeviceProxy
    group_proxy: ZHAGroupProxy | None = dataclasses.field(default=None)

    @property
    def is_group_entity(self) -> bool:
        """Return if this is a group entity."""
        return self.group_proxy is not None and isinstance(self.entity, GroupEntity)


def get_zha_data(hass: HomeAssistant) -> HAZHAData:
    """Get the global ZHA data object."""
    if DATA_ZHA not in hass.data:
        hass.data[DATA_ZHA] = HAZHAData()

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
    ieee_address = next(
        identifier
        for domain, identifier in registry_device.identifiers
        if domain == DOMAIN
    )
    ieee = EUI64.convert(ieee_address)
    return zha_gateway_proxy.device_proxies[ieee]


def cluster_command_schema_to_vol_schema(schema: CommandSchema) -> vol.Schema:
    """Convert a cluster command schema to a voluptuous schema."""
    return vol.Schema(
        {
            (
                vol.Optional(field.name) if field.optional else vol.Required(field.name)
            ): schema_type_to_vol(field.type)
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


@callback
def async_add_entities(
    _async_add_entities: AddEntitiesCallback,
    entity_class: type[ZHAEntity],
    entities: list[EntityData],
    **kwargs,
) -> None:
    """Add entities helper."""
    if not entities:
        return

    entities_to_add = []
    for entity_data in entities:
        try:
            entities_to_add.append(entity_class(entity_data))
        # broad exception to prevent a single entity from preventing an entire platform from loading
        # this can potentially be caused by a misbehaving device or a bad quirk. Not ideal but the
        # alternative is adding try/catch to each entity class __init__ method with a specific exception
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error while adding entity from entity data: %s", entity_data
            )
    _async_add_entities(entities_to_add, update_before_add=False)
    entities.clear()


def _clean_serial_port_path(path: str) -> str:
    """Clean the serial port path, applying corrections where necessary."""

    if path.startswith("socket://"):
        path = path.strip()

    # Removes extraneous brackets from IP addresses (they don't parse in CPython 3.11.4)
    if re.match(r"^socket://\[\d+\.\d+\.\d+\.\d+\]:\d+$", path):
        path = path.replace("[", "").replace("]", "")

    return path


CONF_ZHA_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEFAULT_LIGHT_TRANSITION, default=0): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=2**16 / 10)
        ),
        vol.Required(CONF_ENABLE_ENHANCED_LIGHT_TRANSITION, default=False): cv.boolean,
        vol.Required(CONF_ENABLE_LIGHT_TRANSITIONING_FLAG, default=True): cv.boolean,
        vol.Required(CONF_GROUP_MEMBERS_ASSUME_STATE, default=True): cv.boolean,
        vol.Required(CONF_ENABLE_IDENTIFY_ON_JOIN, default=True): cv.boolean,
        vol.Optional(
            CONF_CONSIDER_UNAVAILABLE_MAINS,
            default=CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS,
        ): cv.positive_int,
        vol.Optional(
            CONF_CONSIDER_UNAVAILABLE_BATTERY,
            default=CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY,
        ): cv.positive_int,
        vol.Required(CONF_ENABLE_MAINS_STARTUP_POLLING, default=True): cv.boolean,
    },
    extra=vol.REMOVE_EXTRA,
)

CONF_ZHA_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ALARM_MASTER_CODE, default="1234"): cv.string,
        vol.Required(CONF_ALARM_FAILED_TRIES, default=3): cv.positive_int,
        vol.Required(CONF_ALARM_ARM_REQUIRES_CODE, default=False): cv.boolean,
    }
)


def create_zha_config(hass: HomeAssistant, ha_zha_data: HAZHAData) -> ZHAData:
    """Create ZHA lib configuration from HA config objects."""

    # ensure that we have the necessary HA configuration data
    assert ha_zha_data.config_entry is not None
    assert ha_zha_data.yaml_config is not None

    # Remove brackets around IP addresses, this no longer works in CPython 3.11.4
    # This will be removed in 2023.11.0
    path = ha_zha_data.config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH]
    cleaned_path = _clean_serial_port_path(path)

    if path != cleaned_path:
        _LOGGER.debug("Cleaned serial port path %r -> %r", path, cleaned_path)
        ha_zha_data.config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH] = cleaned_path
        hass.config_entries.async_update_entry(
            ha_zha_data.config_entry, data=ha_zha_data.config_entry.data
        )

    # deep copy the yaml config to avoid modifying the original and to safely
    # pass it to the ZHA library
    app_config = copy.deepcopy(ha_zha_data.yaml_config.get(CONF_ZIGPY, {}))
    database = app_config.get(
        CONF_DATABASE,
        hass.config.path(DEFAULT_DATABASE_NAME),
    )
    app_config[CONF_DATABASE] = database
    app_config[CONF_DEVICE] = ha_zha_data.config_entry.data[CONF_DEVICE]

    radio_type = RadioType[ha_zha_data.config_entry.data[CONF_RADIO_TYPE]]

    # Until we have a way to coordinate channels with the Thread half of multi-PAN,
    # stick to the old zigpy default of channel 15 instead of dynamically scanning
    if (
        is_multiprotocol_url(app_config[CONF_DEVICE][CONF_DEVICE_PATH])
        and app_config.get(CONF_NWK, {}).get(CONF_NWK_CHANNEL) is None
    ):
        app_config.setdefault(CONF_NWK, {})[CONF_NWK_CHANNEL] = 15

    options: MappingProxyType[str, Any] = ha_zha_data.config_entry.options.get(
        CUSTOM_CONFIGURATION, {}
    )
    zha_options = CONF_ZHA_OPTIONS_SCHEMA(options.get(ZHA_OPTIONS, {}))
    ha_acp_options = CONF_ZHA_ALARM_SCHEMA(options.get(ZHA_ALARM_OPTIONS, {}))
    light_options: LightOptions = LightOptions(
        default_light_transition=zha_options.get(CONF_DEFAULT_LIGHT_TRANSITION),
        enable_enhanced_light_transition=zha_options.get(
            CONF_ENABLE_ENHANCED_LIGHT_TRANSITION
        ),
        enable_light_transitioning_flag=zha_options.get(
            CONF_ENABLE_LIGHT_TRANSITIONING_FLAG
        ),
        group_members_assume_state=zha_options.get(CONF_GROUP_MEMBERS_ASSUME_STATE),
    )
    device_options: DeviceOptions = DeviceOptions(
        enable_identify_on_join=zha_options.get(CONF_ENABLE_IDENTIFY_ON_JOIN),
        consider_unavailable_mains=zha_options.get(CONF_CONSIDER_UNAVAILABLE_MAINS),
        consider_unavailable_battery=zha_options.get(CONF_CONSIDER_UNAVAILABLE_BATTERY),
        enable_mains_startup_polling=zha_options.get(CONF_ENABLE_MAINS_STARTUP_POLLING),
    )
    acp_options: AlarmControlPanelOptions = AlarmControlPanelOptions(
        master_code=ha_acp_options.get(CONF_ALARM_MASTER_CODE),
        failed_tries=ha_acp_options.get(CONF_ALARM_FAILED_TRIES),
        arm_requires_code=ha_acp_options.get(CONF_ALARM_ARM_REQUIRES_CODE),
    )
    coord_config: CoordinatorConfiguration = CoordinatorConfiguration(
        path=app_config[CONF_DEVICE][CONF_DEVICE_PATH],
        baudrate=app_config[CONF_DEVICE][CONF_BAUDRATE],
        flow_control=app_config[CONF_DEVICE][CONF_FLOW_CONTROL],
        radio_type=radio_type.name,
    )
    quirks_config: QuirksConfiguration = QuirksConfiguration(
        enabled=ha_zha_data.yaml_config.get(CONF_ENABLE_QUIRKS, True),
        custom_quirks_path=ha_zha_data.yaml_config.get(CONF_CUSTOM_QUIRKS_PATH),
    )
    overrides_config: dict[str, DeviceOverridesConfiguration] = {}
    overrides: dict[str, dict[str, Any]] = cast(
        dict[str, dict[str, Any]], ha_zha_data.yaml_config.get(CONF_DEVICE_CONFIG)
    )
    if overrides is not None:
        for unique_id, override in overrides.items():
            overrides_config[unique_id] = DeviceOverridesConfiguration(
                type=override["type"],
            )

    return ZHAData(
        zigpy_config=app_config,
        config=ZHAConfiguration(
            light_options=light_options,
            device_options=device_options,
            alarm_control_panel_options=acp_options,
            coordinator_configuration=coord_config,
            quirks_configuration=quirks_config,
            device_overrides=overrides_config,
        ),
        local_timezone=ZoneInfo(hass.config.time_zone),
    )


def convert_zha_error_to_ha_error[**_P, _EntityT: ZHAEntity](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate ZHA commands and re-raises ZHAException as HomeAssistantError."""

    @functools.wraps(func)
    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            return await func(self, *args, **kwargs)
        except ZHAException as err:
            raise HomeAssistantError(err) from err

    return handler


def exclude_none_values(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new dictionary excluding keys with None values."""
    return {k: v for k, v in obj.items() if v is not None}
