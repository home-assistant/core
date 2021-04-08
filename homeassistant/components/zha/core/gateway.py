"""Virtual gateway for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
import collections
from datetime import timedelta
from enum import Enum
import itertools
import logging
import os
import time
import traceback

from serial import SerialException
from zigpy.config import CONF_DEVICE
import zigpy.device as zigpy_dev

from homeassistant.components.system_log import LogEntry, _figure_out_source
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import (
    CONNECTION_ZIGBEE,
    async_get_registry as get_dev_reg,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import (
    async_entries_for_device,
    async_get_registry as get_ent_reg,
)
from homeassistant.helpers.event import async_track_time_interval

from . import discovery, typing as zha_typing
from .const import (
    ATTR_IEEE,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NWK,
    ATTR_SIGNATURE,
    ATTR_TYPE,
    CONF_DATABASE,
    CONF_RADIO_TYPE,
    CONF_ZIGPY,
    DATA_ZHA,
    DATA_ZHA_BRIDGE_ID,
    DATA_ZHA_GATEWAY,
    DEBUG_COMP_BELLOWS,
    DEBUG_COMP_ZHA,
    DEBUG_COMP_ZIGPY,
    DEBUG_COMP_ZIGPY_CC,
    DEBUG_COMP_ZIGPY_DECONZ,
    DEBUG_COMP_ZIGPY_XBEE,
    DEBUG_COMP_ZIGPY_ZIGATE,
    DEBUG_LEVEL_CURRENT,
    DEBUG_LEVEL_ORIGINAL,
    DEBUG_LEVELS,
    DEBUG_RELAY_LOGGERS,
    DEFAULT_DATABASE_NAME,
    DEVICE_PAIRING_STATUS,
    DOMAIN,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_GROUP_MEMBERSHIP_CHANGE,
    SIGNAL_REMOVE,
    UNKNOWN_MANUFACTURER,
    UNKNOWN_MODEL,
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
    ZHA_GW_MSG_LOG_ENTRY,
    ZHA_GW_MSG_LOG_OUTPUT,
    ZHA_GW_MSG_RAW_INIT,
    RadioType,
)
from .device import (
    CONSIDER_UNAVAILABLE_BATTERY,
    CONSIDER_UNAVAILABLE_MAINS,
    DeviceStatus,
    ZHADevice,
)
from .group import GroupMember, ZHAGroup
from .registries import GROUP_ENTITY_DOMAINS
from .store import async_get_registry
from .typing import ZhaGroupType, ZigpyEndpointType, ZigpyGroupType

_LOGGER = logging.getLogger(__name__)

EntityReference = collections.namedtuple(
    "EntityReference",
    "reference_id zha_device cluster_channels device_info remove_future",
)


class DevicePairingStatus(Enum):
    """Status of a device."""

    PAIRED = 1
    INTERVIEW_COMPLETE = 2
    CONFIGURED = 3
    INITIALIZED = 4


class ZHAGateway:
    """Gateway that handles events that happen on the ZHA Zigbee network."""

    def __init__(self, hass, config, config_entry):
        """Initialize the gateway."""
        self._hass = hass
        self._config = config
        self._devices = {}
        self._groups = {}
        self.coordinator_zha_device = None
        self._device_registry = collections.defaultdict(list)
        self.zha_storage = None
        self.ha_device_registry = None
        self.ha_entity_registry = None
        self.application_controller = None
        self.radio_description = None
        self._log_levels = {
            DEBUG_LEVEL_ORIGINAL: async_capture_log_levels(),
            DEBUG_LEVEL_CURRENT: async_capture_log_levels(),
        }
        self.debug_enabled = False
        self._log_relay_handler = LogRelayHandler(hass, self)
        self._config_entry = config_entry
        self._unsubs = []

    async def async_initialize(self):
        """Initialize controller and connect radio."""
        discovery.PROBE.initialize(self._hass)
        discovery.GROUP_PROBE.initialize(self._hass)

        self.zha_storage = await async_get_registry(self._hass)
        self.ha_device_registry = await get_dev_reg(self._hass)
        self.ha_entity_registry = await get_ent_reg(self._hass)

        radio_type = self._config_entry.data[CONF_RADIO_TYPE]

        app_controller_cls = RadioType[radio_type].controller
        self.radio_description = RadioType[radio_type].description

        app_config = self._config.get(CONF_ZIGPY, {})
        database = self._config.get(
            CONF_DATABASE,
            os.path.join(self._hass.config.config_dir, DEFAULT_DATABASE_NAME),
        )
        app_config[CONF_DATABASE] = database
        app_config[CONF_DEVICE] = self._config_entry.data[CONF_DEVICE]

        app_config = app_controller_cls.SCHEMA(app_config)
        try:
            self.application_controller = await app_controller_cls.new(
                app_config, auto_form=True, start_radio=True
            )
        except (asyncio.TimeoutError, SerialException, OSError) as exception:
            _LOGGER.error(
                "Couldn't start %s coordinator",
                self.radio_description,
                exc_info=exception,
            )
            raise ConfigEntryNotReady from exception

        self.application_controller.add_listener(self)
        self.application_controller.groups.add_listener(self)
        self._hass.data[DATA_ZHA][DATA_ZHA_GATEWAY] = self
        self._hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID] = str(
            self.application_controller.ieee
        )
        self.async_load_devices()
        self.async_load_groups()

    @callback
    def async_load_devices(self) -> None:
        """Restore ZHA devices from zigpy application state."""
        for zigpy_device in self.application_controller.devices.values():
            zha_device = self._async_get_or_create_device(zigpy_device, restored=True)
            if zha_device.nwk == 0x0000:
                self.coordinator_zha_device = zha_device
            zha_dev_entry = self.zha_storage.devices.get(str(zigpy_device.ieee))
            delta_msg = "not known"
            if zha_dev_entry and zha_dev_entry.last_seen is not None:
                delta = round(time.time() - zha_dev_entry.last_seen)
                if zha_device.is_mains_powered:
                    zha_device.available = delta < CONSIDER_UNAVAILABLE_MAINS
                else:
                    zha_device.available = delta < CONSIDER_UNAVAILABLE_BATTERY
                delta_msg = f"{str(timedelta(seconds=delta))} ago"
            _LOGGER.debug(
                "[%s](%s) restored as '%s', last seen: %s",
                zha_device.nwk,
                zha_device.name,
                "available" if zha_device.available else "unavailable",
                delta_msg,
            )
        # update the last seen time for devices every 10 minutes to avoid thrashing
        # writes and shutdown issues where storage isn't updated
        self._unsubs.append(
            async_track_time_interval(
                self._hass, self.async_update_device_storage, timedelta(minutes=10)
            )
        )

    @callback
    def async_load_groups(self) -> None:
        """Initialize ZHA groups."""
        for group_id in self.application_controller.groups:
            group = self.application_controller.groups[group_id]
            zha_group = self._async_get_or_create_group(group)
            # we can do this here because the entities are in the entity registry tied to the devices
            discovery.GROUP_PROBE.discover_group_entities(zha_group)

    async def async_initialize_devices_and_entities(self) -> None:
        """Initialize devices and load entities."""
        semaphore = asyncio.Semaphore(2)

        async def _throttle(zha_device: zha_typing.ZhaDeviceType, cached: bool):
            async with semaphore:
                await zha_device.async_initialize(from_cache=cached)

        _LOGGER.debug("Loading battery powered devices")
        await asyncio.gather(
            *[
                _throttle(dev, cached=True)
                for dev in self.devices.values()
                if not dev.is_mains_powered
            ]
        )

        _LOGGER.debug("Loading mains powered devices")
        await asyncio.gather(
            *[
                _throttle(dev, cached=False)
                for dev in self.devices.values()
                if dev.is_mains_powered
            ]
        )

    def device_joined(self, device):
        """Handle device joined.

        At this point, no information about the device is known other than its
        address
        """
        async_dispatcher_send(
            self._hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_JOINED,
                ZHA_GW_MSG_DEVICE_INFO: {
                    ATTR_NWK: device.nwk,
                    ATTR_IEEE: str(device.ieee),
                    DEVICE_PAIRING_STATUS: DevicePairingStatus.PAIRED.name,
                },
            },
        )

    def raw_device_initialized(self, device):
        """Handle a device initialization without quirks loaded."""
        manuf = device.manufacturer
        async_dispatcher_send(
            self._hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_RAW_INIT,
                ZHA_GW_MSG_DEVICE_INFO: {
                    ATTR_NWK: device.nwk,
                    ATTR_IEEE: str(device.ieee),
                    DEVICE_PAIRING_STATUS: DevicePairingStatus.INTERVIEW_COMPLETE.name,
                    ATTR_MODEL: device.model if device.model else UNKNOWN_MODEL,
                    ATTR_MANUFACTURER: manuf if manuf else UNKNOWN_MANUFACTURER,
                    ATTR_SIGNATURE: device.get_signature(),
                },
            },
        )

    def device_initialized(self, device):
        """Handle device joined and basic information discovered."""
        self._hass.async_create_task(self.async_device_initialized(device))

    def device_left(self, device: zigpy_dev.Device):
        """Handle device leaving the network."""
        self.async_update_device(device, False)

    def group_member_removed(
        self, zigpy_group: ZigpyGroupType, endpoint: ZigpyEndpointType
    ) -> None:
        """Handle zigpy group member removed event."""
        # need to handle endpoint correctly on groups
        zha_group = self._async_get_or_create_group(zigpy_group)
        zha_group.info("group_member_removed - endpoint: %s", endpoint)
        self._send_group_gateway_message(zigpy_group, ZHA_GW_MSG_GROUP_MEMBER_REMOVED)
        async_dispatcher_send(
            self._hass, f"{SIGNAL_GROUP_MEMBERSHIP_CHANGE}_0x{zigpy_group.group_id:04x}"
        )

    def group_member_added(
        self, zigpy_group: ZigpyGroupType, endpoint: ZigpyEndpointType
    ) -> None:
        """Handle zigpy group member added event."""
        # need to handle endpoint correctly on groups
        zha_group = self._async_get_or_create_group(zigpy_group)
        zha_group.info("group_member_added - endpoint: %s", endpoint)
        self._send_group_gateway_message(zigpy_group, ZHA_GW_MSG_GROUP_MEMBER_ADDED)
        async_dispatcher_send(
            self._hass, f"{SIGNAL_GROUP_MEMBERSHIP_CHANGE}_0x{zigpy_group.group_id:04x}"
        )
        if len(zha_group.members) == 2:
            # we need to do this because there wasn't already a group entity to remove and re-add
            discovery.GROUP_PROBE.discover_group_entities(zha_group)

    def group_added(self, zigpy_group: ZigpyGroupType) -> None:
        """Handle zigpy group added event."""
        zha_group = self._async_get_or_create_group(zigpy_group)
        zha_group.info("group_added")
        # need to dispatch for entity creation here
        self._send_group_gateway_message(zigpy_group, ZHA_GW_MSG_GROUP_ADDED)

    def group_removed(self, zigpy_group: ZigpyGroupType) -> None:
        """Handle zigpy group removed event."""
        self._send_group_gateway_message(zigpy_group, ZHA_GW_MSG_GROUP_REMOVED)
        zha_group = self._groups.pop(zigpy_group.group_id, None)
        zha_group.info("group_removed")
        self._cleanup_group_entity_registry_entries(zigpy_group)

    def _send_group_gateway_message(
        self, zigpy_group: ZigpyGroupType, gateway_message_type: str
    ) -> None:
        """Send the gateway event for a zigpy group event."""
        zha_group = self._groups.get(zigpy_group.group_id)
        if zha_group is not None:
            async_dispatcher_send(
                self._hass,
                ZHA_GW_MSG,
                {
                    ATTR_TYPE: gateway_message_type,
                    ZHA_GW_MSG_GROUP_INFO: zha_group.group_info,
                },
            )

    async def _async_remove_device(self, device, entity_refs):
        if entity_refs is not None:
            remove_tasks = []
            for entity_ref in entity_refs:
                remove_tasks.append(entity_ref.remove_future)
            if remove_tasks:
                await asyncio.wait(remove_tasks)
        reg_device = self.ha_device_registry.async_get(device.device_id)
        if reg_device is not None:
            self.ha_device_registry.async_remove_device(reg_device.id)

    def device_removed(self, device):
        """Handle device being removed from the network."""
        zha_device = self._devices.pop(device.ieee, None)
        entity_refs = self._device_registry.pop(device.ieee, None)
        if zha_device is not None:
            device_info = zha_device.zha_device_info
            zha_device.async_cleanup_handles()
            async_dispatcher_send(
                self._hass, "{}_{}".format(SIGNAL_REMOVE, str(zha_device.ieee))
            )
            asyncio.ensure_future(self._async_remove_device(zha_device, entity_refs))
            if device_info is not None:
                async_dispatcher_send(
                    self._hass,
                    ZHA_GW_MSG,
                    {
                        ATTR_TYPE: ZHA_GW_MSG_DEVICE_REMOVED,
                        ZHA_GW_MSG_DEVICE_INFO: device_info,
                    },
                )

    def get_device(self, ieee):
        """Return ZHADevice for given ieee."""
        return self._devices.get(ieee)

    def get_group(self, group_id: str) -> ZhaGroupType | None:
        """Return Group for given group id."""
        return self.groups.get(group_id)

    @callback
    def async_get_group_by_name(self, group_name: str) -> ZhaGroupType | None:
        """Get ZHA group by name."""
        for group in self.groups.values():
            if group.name == group_name:
                return group
        return None

    def get_entity_reference(self, entity_id):
        """Return entity reference for given entity_id if found."""
        for entity_reference in itertools.chain.from_iterable(
            self.device_registry.values()
        ):
            if entity_id == entity_reference.reference_id:
                return entity_reference

    def remove_entity_reference(self, entity):
        """Remove entity reference for given entity_id if found."""
        if entity.zha_device.ieee in self.device_registry:
            entity_refs = self.device_registry.get(entity.zha_device.ieee)
            self.device_registry[entity.zha_device.ieee] = [
                e for e in entity_refs if e.reference_id != entity.entity_id
            ]

    def _cleanup_group_entity_registry_entries(
        self, zigpy_group: ZigpyGroupType
    ) -> None:
        """Remove entity registry entries for group entities when the groups are removed from HA."""
        # first we collect the potential unique ids for entities that could be created from this group
        possible_entity_unique_ids = [
            f"{domain}_zha_group_0x{zigpy_group.group_id:04x}"
            for domain in GROUP_ENTITY_DOMAINS
        ]

        # then we get all group entity entries tied to the coordinator
        all_group_entity_entries = async_entries_for_device(
            self.ha_entity_registry,
            self.coordinator_zha_device.device_id,
            include_disabled_entities=True,
        )

        # then we get the entity entries for this specific group by getting the entries that match
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
            self.ha_entity_registry.async_remove(entry.entity_id)

    @property
    def devices(self):
        """Return devices."""
        return self._devices

    @property
    def groups(self):
        """Return groups."""
        return self._groups

    @property
    def device_registry(self):
        """Return entities by ieee."""
        return self._device_registry

    def register_entity_reference(
        self,
        ieee,
        reference_id,
        zha_device,
        cluster_channels,
        device_info,
        remove_future,
    ):
        """Record the creation of a hass entity associated with ieee."""
        self._device_registry[ieee].append(
            EntityReference(
                reference_id=reference_id,
                zha_device=zha_device,
                cluster_channels=cluster_channels,
                device_info=device_info,
                remove_future=remove_future,
            )
        )

    @callback
    def async_enable_debug_mode(self, filterer=None):
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
    def async_disable_debug_mode(self, filterer=None):
        """Disable debug mode for ZHA."""
        async_set_logger_levels(self._log_levels[DEBUG_LEVEL_ORIGINAL])
        self._log_levels[DEBUG_LEVEL_CURRENT] = async_capture_log_levels()
        for logger_name in DEBUG_RELAY_LOGGERS:
            logging.getLogger(logger_name).removeHandler(self._log_relay_handler)
        if filterer:
            self._log_relay_handler.removeFilter(filterer)
        self.debug_enabled = False

    @callback
    def _async_get_or_create_device(
        self, zigpy_device: zha_typing.ZigpyDeviceType, restored: bool = False
    ):
        """Get or create a ZHA device."""
        zha_device = self._devices.get(zigpy_device.ieee)
        if zha_device is None:
            zha_device = ZHADevice.new(self._hass, zigpy_device, self, restored)
            self._devices[zigpy_device.ieee] = zha_device
            device_registry_device = self.ha_device_registry.async_get_or_create(
                config_entry_id=self._config_entry.entry_id,
                connections={(CONNECTION_ZIGBEE, str(zha_device.ieee))},
                identifiers={(DOMAIN, str(zha_device.ieee))},
                name=zha_device.name,
                manufacturer=zha_device.manufacturer,
                model=zha_device.model,
            )
            zha_device.set_device_id(device_registry_device.id)
        entry = self.zha_storage.async_get_or_create_device(zha_device)
        zha_device.async_update_last_seen(entry.last_seen)
        return zha_device

    @callback
    def _async_get_or_create_group(self, zigpy_group: ZigpyGroupType) -> ZhaGroupType:
        """Get or create a ZHA group."""
        zha_group = self._groups.get(zigpy_group.group_id)
        if zha_group is None:
            zha_group = ZHAGroup(self._hass, self, zigpy_group)
            self._groups[zigpy_group.group_id] = zha_group
        return zha_group

    @callback
    def async_update_device(
        self, sender: zigpy_dev.Device, available: bool = True
    ) -> None:
        """Update device that has just become available."""
        if sender.ieee in self.devices:
            device = self.devices[sender.ieee]
            # avoid a race condition during new joins
            if device.status is DeviceStatus.INITIALIZED:
                device.update_available(available)

    async def async_update_device_storage(self, *_):
        """Update the devices in the store."""
        for device in self.devices.values():
            self.zha_storage.async_update_device(device)

    async def async_device_initialized(self, device: zha_typing.ZigpyDeviceType):
        """Handle device joined and basic information discovered (async)."""
        zha_device = self._async_get_or_create_device(device)
        # This is an active device so set a last seen if it is none
        if zha_device.last_seen is None:
            zha_device.async_update_last_seen(time.time())
        _LOGGER.debug(
            "device - %s:%s entering async_device_initialized - is_new_join: %s",
            device.nwk,
            device.ieee,
            zha_device.status is not DeviceStatus.INITIALIZED,
        )

        if zha_device.status is DeviceStatus.INITIALIZED:
            # ZHA already has an initialized device so either the device was assigned a
            # new nwk or device was physically reset and added again without being removed
            _LOGGER.debug(
                "device - %s:%s has been reset and re-added or its nwk address changed",
                device.nwk,
                device.ieee,
            )
            await self._async_device_rejoined(zha_device)
        else:
            _LOGGER.debug(
                "device - %s:%s has joined the ZHA zigbee network",
                device.nwk,
                device.ieee,
            )
            await self._async_device_joined(zha_device)

        device_info = zha_device.zha_device_info
        device_info[DEVICE_PAIRING_STATUS] = DevicePairingStatus.INITIALIZED.name
        async_dispatcher_send(
            self._hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_FULL_INIT,
                ZHA_GW_MSG_DEVICE_INFO: device_info,
            },
        )

    async def _async_device_joined(self, zha_device: zha_typing.ZhaDeviceType) -> None:
        zha_device.available = True
        device_info = zha_device.device_info
        await zha_device.async_configure()
        device_info[DEVICE_PAIRING_STATUS] = DevicePairingStatus.CONFIGURED.name
        async_dispatcher_send(
            self._hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_FULL_INIT,
                ZHA_GW_MSG_DEVICE_INFO: device_info,
            },
        )
        await zha_device.async_initialize(from_cache=False)
        async_dispatcher_send(self._hass, SIGNAL_ADD_ENTITIES)

    async def _async_device_rejoined(self, zha_device):
        _LOGGER.debug(
            "skipping discovery for previously discovered device - %s:%s",
            zha_device.nwk,
            zha_device.ieee,
        )
        # we don't have to do this on a nwk swap but we don't have a way to tell currently
        await zha_device.async_configure()
        device_info = zha_device.device_info
        device_info[DEVICE_PAIRING_STATUS] = DevicePairingStatus.CONFIGURED.name
        async_dispatcher_send(
            self._hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_FULL_INIT,
                ZHA_GW_MSG_DEVICE_INFO: device_info,
            },
        )
        # force async_initialize() to fire so don't explicitly call it
        zha_device.available = False
        zha_device.update_available(True)

    async def async_create_zigpy_group(
        self, name: str, members: list[GroupMember]
    ) -> ZhaGroupType:
        """Create a new Zigpy Zigbee group."""
        # we start with two to fill any gaps from a user removing existing groups
        group_id = 2
        while group_id in self.groups:
            group_id += 1

        # guard against group already existing
        if self.async_get_group_by_name(name) is None:
            self.application_controller.groups.add_group(group_id, name)
            if members is not None:
                tasks = []
                for member in members:
                    _LOGGER.debug(
                        "Adding member with IEEE: %s and endpoint ID: %s to group: %s:0x%04x",
                        member.ieee,
                        member.endpoint_id,
                        name,
                        group_id,
                    )
                    tasks.append(
                        self.devices[member.ieee].async_add_endpoint_to_group(
                            member.endpoint_id, group_id
                        )
                    )
                await asyncio.gather(*tasks)
        return self.groups.get(group_id)

    async def async_remove_zigpy_group(self, group_id: int) -> None:
        """Remove a Zigbee group from Zigpy."""
        group = self.groups.get(group_id)
        if not group:
            _LOGGER.debug("Group: %s:0x%04x could not be found", group.name, group_id)
            return
        if group.members:
            tasks = []
            for member in group.members:
                tasks.append(member.async_remove_from_group())
            if tasks:
                await asyncio.gather(*tasks)
        self.application_controller.groups.pop(group_id)

    async def shutdown(self):
        """Stop ZHA Controller Application."""
        _LOGGER.debug("Shutting down ZHA ControllerApplication")
        for unsubscribe in self._unsubs:
            unsubscribe()
        await self.application_controller.pre_shutdown()

    def handle_message(
        self,
        sender: zigpy_dev.Device,
        profile: int,
        cluster: int,
        src_ep: int,
        dst_ep: int,
        message: bytes,
    ) -> None:
        """Handle message from a device Event handler."""
        if sender.ieee in self.devices and not self.devices[sender.ieee].available:
            self.async_update_device(sender, available=True)


@callback
def async_capture_log_levels():
    """Capture current logger levels for ZHA."""
    return {
        DEBUG_COMP_BELLOWS: logging.getLogger(DEBUG_COMP_BELLOWS).getEffectiveLevel(),
        DEBUG_COMP_ZHA: logging.getLogger(DEBUG_COMP_ZHA).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY: logging.getLogger(DEBUG_COMP_ZIGPY).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_CC: logging.getLogger(DEBUG_COMP_ZIGPY_CC).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_DECONZ: logging.getLogger(
            DEBUG_COMP_ZIGPY_DECONZ
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_XBEE: logging.getLogger(
            DEBUG_COMP_ZIGPY_XBEE
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_ZIGATE: logging.getLogger(
            DEBUG_COMP_ZIGPY_ZIGATE
        ).getEffectiveLevel(),
    }


@callback
def async_set_logger_levels(levels):
    """Set logger levels for ZHA."""
    logging.getLogger(DEBUG_COMP_BELLOWS).setLevel(levels[DEBUG_COMP_BELLOWS])
    logging.getLogger(DEBUG_COMP_ZHA).setLevel(levels[DEBUG_COMP_ZHA])
    logging.getLogger(DEBUG_COMP_ZIGPY).setLevel(levels[DEBUG_COMP_ZIGPY])
    logging.getLogger(DEBUG_COMP_ZIGPY_CC).setLevel(levels[DEBUG_COMP_ZIGPY_CC])
    logging.getLogger(DEBUG_COMP_ZIGPY_DECONZ).setLevel(levels[DEBUG_COMP_ZIGPY_DECONZ])
    logging.getLogger(DEBUG_COMP_ZIGPY_XBEE).setLevel(levels[DEBUG_COMP_ZIGPY_XBEE])
    logging.getLogger(DEBUG_COMP_ZIGPY_ZIGATE).setLevel(levels[DEBUG_COMP_ZIGPY_ZIGATE])


class LogRelayHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(self, hass, gateway):
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.hass = hass
        self.gateway = gateway

    def emit(self, record):
        """Relay log message via dispatcher."""
        stack = []
        if record.levelno >= logging.WARN and not record.exc_info:
            stack = [f for f, _, _, _ in traceback.extract_stack()]

        entry = LogEntry(record, stack, _figure_out_source(record, stack, self.hass))
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {ATTR_TYPE: ZHA_GW_MSG_LOG_OUTPUT, ZHA_GW_MSG_LOG_ENTRY: entry.to_dict()},
        )
