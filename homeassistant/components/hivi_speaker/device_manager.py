from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from enum import Enum
from typing import Dict, List, Optional, Callable
import asyncio
from datetime import datetime
from .device import SyncGroupStatus, ConnectionStatus, HIVIDevice, SlaveDeviceInfo
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from .const import (
    DISCOVERY_BASE_INTERVAL,
    DOMAIN,
    SIGNAL_DEVICE_DISCOVERED,
    DEVICE_OFFLINE_THRESHOLD,
)
import socket
import time
import aiohttp
import xml.etree.ElementTree as ET
import async_timeout
from typing import Set
from .discovery_scheduler import HIVIDiscoveryScheduler
from .group_coordinator import HIVIGroupCoordinator
from hivico import HivicoClient
from .device_data_registry import DeviceDataRegistry

_LOGGER = logging.getLogger(__name__)


class HIVIDeviceManager:
    """Device manager, responsible for device discovery, status updates, and entity creation"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        from .switch import HIVISlaveControlSwitchHub
        from .media_player import HIVIMediaPlayerEntityHub

        self.hass = hass
        self.config_entry = config_entry
        # Core components
        self.device_data_registry = DeviceDataRegistry(
            hass=hass
        )  # Assigned after external initialization
        self.hivi_slave_control_switch_hub = HIVISlaveControlSwitchHub(
            hass=hass, entry=config_entry
        )
        self.hivi_media_player_entity_hub = HIVIMediaPlayerEntityHub(
            hass=hass, entry=config_entry
        )

        # New components
        self.discovery_scheduler = HIVIDiscoveryScheduler(
            hass=hass,
            config_entry=config_entry,
            device_manager=self,
            base_interval=DISCOVERY_BASE_INTERVAL,
        )
        self.group_coordinator = HIVIGroupCoordinator(
            hass=hass, device_manager=self, discovery_scheduler=self.discovery_scheduler
        )

        # Store callbacks for each platform
        self._add_entities_callbacks = {}

        self._discovery_queue = asyncio.Queue()
        self._handle_discovery_worker = hass.loop.create_task(
            self._handle_discovery_loop()
        )

    def set_add_entities_callback(self, platform: str, callback: AddEntitiesCallback):
        """Set callback for adding entities"""
        self._add_entities_callbacks[platform] = callback

    async def async_setup(self):
        """Initialize setup"""

        # Load device data
        await self.device_data_registry.async_load()

        # Register dispatcher callbacks
        # Subscribe first, then start scheduler to prevent missing discovery events
        self._unsub_discovery = async_dispatcher_connect(
            self.hass, SIGNAL_DEVICE_DISCOVERED, self._discovery_enqueue
        )

        # Start components
        await self.discovery_scheduler.async_start()
        await self.group_coordinator.async_start()

    # Changed to coroutine callback
    async def _discovery_enqueue(self, discovered_devices: dict):
        await self._discovery_queue.put(discovered_devices)

    async def _handle_discovery_loop(self):
        while True:
            discovered_devices = await self._discovery_queue.get()
            try:
                await self._handle_discovered_devices(discovered_devices)
            except Exception as e:
                _LOGGER.exception("error handling discovered devices: %s", e)
            finally:
                self._discovery_queue.task_done()

    async def _handle_discovered_devices(self, discovered_devices: List[Dict]):
        """Handle discovered devices"""
        _LOGGER.debug("discovered devices: %s", discovered_devices)
        # # Discovered: {UDN: device_info}
        # for udn, info in discovered.items():
        #     # Merge/update internal table of device_manager, create entities or update IPs, etc.
        #     self._devices[udn] = info
        #     # For example: create or update corresponding entities
        #     await self._ensure_device_registered(udn, info)

        """
        1. Incremental saving. Discovered devices are incrementally saved to self.device_manager.registry.devices.
        2. Device status information update. Traverse all devices in self.device_manager.registry.devices, call the HTTP getStatusEx interface to get the status information of each device, and also update it to these devices.
        3. Add or remove switches. Based on the latest number of devices, update the switches each device should have. Delete excess ones and add missing ones.
        4. Based on the association status of the latest devices, update the status of media players and switches.
        5. For devices that originally existed but were not discovered by SSDP this time, calculate their offline duration. If it exceeds the threshold, set the device and its entities as unavailable.
        """

        # Incremental saving
        await self._save_discovered_devices(discovered_devices)
        # _LOGGER.debug("_save_discovered_devices completed saving")
        # Device status information update
        await self._update_all_device_statuses()
        # # _LOGGER.debug("_update_all_device_statuses completed updating")
        # # Register devices to HA and delete non-existent devices
        # await self._register_and_unregister_device()
        # # Media player
        await self._add_media_player()
        # # Add or remove switches
        await self._add_or_remove_switches()
        # # _LOGGER.debug("_add_or_remove_switches completed adding or removing switches")
        # # # Update media player and switch status
        await self._update_device_entity_states()
        # _LOGGER.debug("_update_device_entity_states completed updating entity states")
        # # Handle offline devices
        await self._device_offline_process()
        # _LOGGER.debug("_device_offline_process completed offline processing")

    async def _save_discovered_devices(self, discovered_devices: list[dict]):
        """Incrementally save discovered devices"""
        idx = 0
        for device_info in discovered_devices:
            speaker_device_id = device_info.get("UDN")
            idx += 1
            _LOGGER.debug(
                "process discovered device #%d: UDN=%s", idx, speaker_device_id
            )
            if not speaker_device_id:
                _LOGGER.debug("device_info has no UDN so no speaker_device_id")
                continue

            device_dict = (
                self.device_data_registry.get_device_dict_by_speaker_device_id(
                    speaker_device_id
                )
            )
            if device_dict:
                _LOGGER.debug(
                    "already exist, will update: speaker_device_id = %s",
                    speaker_device_id,
                )
                device_obj = HIVIDevice(**device_dict)
                if device_obj:
                    ha_device_id = device_obj.ha_device_id
                    device_obj.ip_addr = device_info.get("ip_addr", device_obj.ip_addr)
                    device_obj.mac_address = device_info.get(
                        "mac_address", device_obj.mac_address
                    )
                    device_obj.hostname = device_info.get(
                        "hostname", device_obj.hostname
                    )
                    device_obj.friendly_name = device_info.get(
                        "friendly_name", device_obj.friendly_name
                    )
                    device_obj.model = device_info.get("model_name", device_obj.model)
                    device_obj.manufacturer = device_info.get(
                        "manufacturer", device_obj.manufacturer
                    )
                    # Update existing device information
                    device_dict_new = device_obj.model_dump()
                    # Save to device data registry
                    self.device_data_registry.set_device_dict_by_ha_device_id(
                        ha_device_id, device_dict_new
                    )
                else:
                    _LOGGER.warning("device_dict convert result is None")
            else:
                _LOGGER.debug(
                    "not yet exist, will add：speaker_device_id = %s", speaker_device_id
                )
                # Create device object
                device_obj = self._create_device_obj_from_discovered_device_info(
                    device_info
                )
                # add new device
                ha_device_id = await self.async_register_device(device_obj)
                if ha_device_id:
                    device_obj.ha_device_id = ha_device_id
                    # Save to device data registry
                    device_dict = device_obj.model_dump()
                    self.device_data_registry.set_device_dict_by_ha_device_id(
                        ha_device_id, device_dict
                    )
                else:
                    _LOGGER.warning("ha_device_id is None after register to ha")

    async def _update_all_device_statuses(self):
        """Update status information of all devices"""
        slave_device_uuid_set = set()
        can_fetch_status_devices = set()
        can_not_fetch_status_devices = set()

        ha_device_list = await self._get_devices_for_device()

        # Prepare coroutines for batch fetching device status
        device_status_tasks = []
        device_info_list = []  # Save correspondence between devices and related information

        for ha_device in ha_device_list:
            ha_device_id = ha_device.id
            device_dict = self.device_data_registry.get_device_dict_by_ha_device_id(
                ha_device_id=ha_device_id, default=None
            )
            if device_dict is None:
                _LOGGER.warning(
                    "can not get device_dict from ha_device_id skip updating devcie statues: ha_device_id = %s",
                    ha_device_id,
                )
                continue

            device_obj = HIVIDevice(**device_dict)

            # Create asynchronous tasks for each device
            device_info_list.append(
                {
                    "ha_device": ha_device,
                    "ha_device_id": ha_device_id,
                    "device_obj": device_obj,
                    "device_dict": device_dict,
                }
            )

            # Create asynchronous tasks but do not execute immediately
            device_status_tasks.append(self._fetch_device_status(device_obj))

        # Execute all device status fetching requests in parallel in batches
        device_statuses = await asyncio.gather(
            *device_status_tasks, return_exceptions=True
        )

        # Process return results of all devices
        for idx, (device_info, device_status_or_exc) in enumerate(
            zip(device_info_list, device_statuses)
        ):
            ha_device_id = device_info["ha_device_id"]
            device_obj = device_info["device_obj"]

            if isinstance(device_status_or_exc, Exception):
                _LOGGER.error(
                    "failed to get device status: %s error: %s",
                    device_obj.friendly_name,
                    str(device_status_or_exc),
                )
                device_status = None
            else:
                device_status = device_status_or_exc

            if device_status:
                # Update device status
                device_obj.last_seen = datetime.now()
                device_obj.connection_status = ConnectionStatus.ONLINE
                device_obj.wifi_channel = device_status.get("WifiChannel")
                device_obj.ssid = device_status.get("ssid")
                device_obj.auth_mode = device_status.get("auth")
                device_obj.encryption_mode = device_status.get("encry")
                device_obj.psk = device_status.get("psk")
                device_obj.uuid = device_status.get("uuid")
                device_obj.hardware = device_status.get("hardware", "")

                group = device_status.get("group", 0)
                if group == 1:
                    device_obj.sync_group_status = SyncGroupStatus.SLAVE
                else:
                    try:
                        # Get slave device list
                        slave_device_result = await self._fetch_slave_device(device_obj)
                    except Exception as e:
                        _LOGGER.error(
                            "failed to get slave device list for %s error: %s",
                            device_obj.friendly_name,
                            str(e),
                        )
                        slave_device_result = None

                    # Update more device attributes based on slave_device_result
                    slave_device_obj_list = []
                    if slave_device_result:
                        slave_device_num = slave_device_result.get("slaves", 0)
                        slave_device_dict_list = slave_device_result.get(
                            "slave_list", []
                        )
                        for slave_device_dict in slave_device_dict_list:
                            slave_device_dict["friendly_name"] = slave_device_dict.get(
                                "name", ""
                            )
                            slave_device_dict["ip_addr"] = slave_device_dict.get(
                                "ip", ""
                            )
                            del slave_device_dict["name"]
                            del slave_device_dict["ip"]
                            slave_device_obj = SlaveDeviceInfo(**slave_device_dict)
                            slave_device_obj_list.append(slave_device_obj)

                        device_obj.slave_device_num = slave_device_num
                        device_obj.slave_device_list = slave_device_obj_list
                        if slave_device_num > 0:
                            device_obj.sync_group_status = SyncGroupStatus.MASTER
                            for slave_device in slave_device_obj_list:
                                slave_device_uuid_set.add(slave_device.uuid)
                        else:
                            device_obj.sync_group_status = SyncGroupStatus.STANDALONE
                    else:
                        device_obj.sync_group_status = SyncGroupStatus.STANDALONE

                device_dict_new = device_obj.model_dump()
                # Save to device data registry
                self.device_data_registry.set_device_dict_by_ha_device_id(
                    ha_device_id,
                    device_dict_new,
                )
                can_fetch_status_devices.add(ha_device_id)
            else:
                can_not_fetch_status_devices.add(ha_device_id)

        # Delete slave devices
        for ha_device in ha_device_list:
            ha_device_id = ha_device.id

            # Get device identifiers
            target_unique_id = None
            for domain, unique_id in ha_device.identifiers:
                if domain == DOMAIN:
                    target_unique_id = unique_id
                    break
            if target_unique_id is None:
                continue

            if target_unique_id in slave_device_uuid_set:
                _LOGGER.debug(
                    "device %s (%s) is recognized as a slave device, will delete its device and entities",
                    ha_device.name,
                    target_unique_id,
                )
                await self.async_remove_device_with_entities(ha_device_id)

    async def async_remove_device_with_entities(self, ha_device_id):
        """Safely delete device and all its entities"""
        hass = self.hass

        try:
            # Get registries
            ent_reg = er.async_get(hass)
            dev_reg = dr.async_get(hass)

            # Get entities to be deleted
            device_entities = ent_reg.entities.get_entries_for_device_id(ha_device_id)

            if not device_entities:
                _LOGGER.debug(
                    "device %s has no entity, it will be deleted directly", ha_device_id
                )
                dev_reg.async_remove_device(ha_device_id)
                return

            # First delete all entities
            entity_ids = []
            for entity_entry in device_entities:
                entity_id = entity_entry.entity_id
                ent_reg.async_remove(entity_id)
                entity_ids.append(entity_id)

            _LOGGER.debug("deleted entities: %s", entity_ids)

            # Then delete the device
            dev_reg.async_remove_device(ha_device_id)
            _LOGGER.debug("deleted device: %s", ha_device_id)

            # # Manually trigger update events
            # hass.bus.async_fire("entity_registry_updated", {})
            # hass.bus.async_fire("device_registry_updated", {})

        except Exception as err:
            _LOGGER.error("error when deleting device: %s", err, exc_info=True)

    async def _fetch_device_status(self, device_obj: HIVIDevice):
        """Get device status through HTTP interface"""
        ip_addr = device_obj.ip_addr
        # device_status = await get_device_status(ip_addr)
        async with HivicoClient(timeout=5, debug=True) as client:
            device_status = await client.get_device_status(ip_addr)
            if device_status:
                _LOGGER.debug(f"device status: {device_status}")
        return device_status

    async def _fetch_slave_device(self, device_obj: HIVIDevice):
        """Get device status through HTTP interface"""
        ip_addr = device_obj.ip_addr
        async with HivicoClient(timeout=5, debug=True) as client:
            slave_device_result = await client.get_slave_devices(ip_addr)
        return slave_device_result

    async def _add_media_player(self):
        """Add media player entities"""

        from .media_player import HIVIMediaPlayerEntity

        ha_device_list = await self._get_devices_for_device()
        for ha_device in ha_device_list:
            existing_entiy_entry_list = await self._get_entities_for_device(
                ha_device.id
            )
            # _LOGGER.debug("Device %s existing entities: %s", ha_device.id, existing_entiy_entry_list)

            device_dict = self.device_data_registry.get_device_dict_by_ha_device_id(
                ha_device.id, default=None
            )
            if device_dict is None:
                _LOGGER.warning(
                    "can not get device_dict from ha_device_id skip updating devcie statues: ha_device_id = %s",
                    ha_device.id,
                )
                continue

            device_obj = HIVIDevice(**device_dict)

            need_to_add_media_player_flg = True
            media_player_entity_exist_flg = False
            for entity_entry in existing_entiy_entry_list:
                _LOGGER.debug(
                    "check %s 's entity: %s",
                    device_obj.friendly_name,
                    entity_entry.entity_id,
                )
                if entity_entry.entity_id.startswith(
                    "media_player."
                ) and entity_entry.unique_id.startswith(
                    f"{device_obj.speaker_device_id}"
                ):
                    media_player_entity_exist_flg = True
                    break

            if media_player_entity_exist_flg:
                _LOGGER.debug(
                    "device %s already has media player, will check state",
                    device_obj.friendly_name,
                )

                entity_id = entity_entry.entity_id
                state_obj = self.hass.states.get(entity_id)
                if not state_obj:
                    _LOGGER.debug(
                        "entity %s has no state (possibly not initialized)", entity_id
                    )
                    need_to_add_media_player_flg = True
                else:
                    if state_obj.state == "unavailable":
                        _LOGGER.debug("entity %s is unavailable", entity_id)
                        # need_to_add_media_player_flg = False
                        media_player = (
                            self.hivi_media_player_entity_hub.get_media_player(
                                entity_entry.unique_id
                            )
                        )
                        if media_player:
                            _LOGGER.debug("update media state %s", entity_id)
                            need_to_add_media_player_flg = False
                        else:
                            _LOGGER.debug(
                                "can not get media player entity by unique_id %s",
                                entity_entry.unique_id,
                            )
                            need_to_add_media_player_flg = True
                    else:
                        _LOGGER.debug("entity %s is available", entity_id)
                        need_to_add_media_player_flg = False

            if not need_to_add_media_player_flg:
                _LOGGER.debug(
                    "device %s media player entity is available, skip adding",
                    device_obj.friendly_name,
                )
                continue

            device_obj = HIVIDevice(**device_dict)

            media_player_entity = HIVIMediaPlayerEntity(
                hass=self.hass,
                hub=self.hivi_media_player_entity_hub,
                device_manager=self,
                device=device_obj,
            )
            media_cb = self._add_entities_callbacks.get("media_player")
            if media_cb:
                media_cb([media_player_entity], update_before_add=False)
            else:
                _LOGGER.debug(
                    "no 'media_player' add callback, skip adding media player entity"
                )

    async def _add_or_remove_switches(self):
        """Create or delete switch entities for controlling other speakers for each device"""
        from .switch import HIVISlaveControlSwitch

        ha_device_list = await self._get_devices_for_device()

        for ha_device in ha_device_list:
            existing_entiy_entry_list = await self._get_entities_for_device(
                ha_device.id
            )
            # _LOGGER.debug("Device %s existing entities: %s", ha_device.id, existing_entiy_entry_list)

            device_dict = self.device_data_registry.get_device_dict_by_ha_device_id(
                ha_device.id, default=None
            )
            if device_dict is None:
                _LOGGER.warning(
                    "can not get device_dict from ha_device_id skip updating devcie statues: ha_device_id = %s",
                    ha_device.id,
                )
                continue

            device_obj = HIVIDevice(**device_dict)
            slave_speaker_device_id_to_entity_entry_dict = dict()
            should_remove_entity_id_set = set()
            # slave_speaker_device_id_set = set()
            for entity_entry in existing_entiy_entry_list:
                _LOGGER.debug(
                    "check %s 's entity: %s",
                    device_obj.friendly_name,
                    entity_entry.entity_id,
                )
                if entity_entry.entity_id.startswith(
                    "switch."
                ) and entity_entry.unique_id.startswith(
                    f"{device_obj.speaker_device_id}_slave_"
                ):
                    slave_speaker_device_id = entity_entry.unique_id.split("_slave_")[
                        -1
                    ]
                    # slave_speaker_device_id_set.add(slave_speaker_device_id)
                    slave_speaker_device_id_to_entity_entry_dict[
                        slave_speaker_device_id
                    ] = entity_entry
                    device_dict_slave = (
                        self.device_data_registry.get_device_dict_by_speaker_device_id(
                            slave_speaker_device_id, default=None
                        )
                    )
                    if device_dict_slave is None:
                        # The device of the sub-sub device does not exist, but need to determine if it has become a slave device
                        _LOGGER.debug(
                            "device %s's slave speaker %s device data does not exist, but need to determine if it is a slave device",
                            device_obj.friendly_name,
                            slave_speaker_device_id,
                        )
                        should_remove_flg = True
                        slave_device_list = device_obj.slave_device_list
                        for slave_device in slave_device_list:
                            if slave_device.uuid == slave_speaker_device_id:
                                _LOGGER.debug(
                                    "device %s's slave speaker list contains uuid: %s, keep its switch entity",
                                    device_obj.friendly_name,
                                    slave_speaker_device_id,
                                )
                                should_remove_flg = False
                        if should_remove_flg:
                            _LOGGER.debug(
                                "remove %s 's invalid slave device: %s",
                                device_obj.friendly_name,
                                entity_entry.entity_id,
                            )
                            should_remove_entity_id_set.add(entity_entry.entity_id)

            keys = slave_speaker_device_id_to_entity_entry_dict.keys()
            _LOGGER.debug(
                f"slave_speaker_device_id_to_entity_entry_dict.keys() = {keys}"
            )

            # Delete switches that no longer exist for corresponding devices
            entity_registry = er.async_get(self.hass)
            for entity_id in should_remove_entity_id_set:
                entity_registry.async_remove(entity_id)

            # Get all controllable speakers
            available_slave_dict_list = (
                self.device_data_registry.get_available_slave_device_dict_list(
                    device_obj.speaker_device_id
                )
            )
            _LOGGER.debug(
                "device %s can control slave speaker count: %d",
                device_obj.friendly_name,
                len(available_slave_dict_list),
            )
            switches = []
            # Add based on other device existence
            for slave_candidate_dict in available_slave_dict_list:
                # _LOGGER.debug(f"slave_candidate_dict = {slave_candidate_dict}")
                slave_candidate_obj = HIVIDevice(**slave_candidate_dict)
                _LOGGER.debug(
                    "prepare to create %s 's slave device %s 's switch",
                    device_obj.friendly_name,
                    slave_candidate_obj.friendly_name,
                )
                # Master speaker's hardware
                hardware_1 = device_obj.hardware.lower() if device_obj.hardware else ""
                # Slave speaker's hardware
                hardware_2 = (
                    slave_candidate_obj.hardware.lower()
                    if slave_candidate_obj.hardware
                    else ""
                )
                # Check hardware compatibility
                if hardware_1 and hardware_2:
                    if hardware_1.startswith("swan"):
                        _LOGGER.debug("master is swan type")
                        if hardware_2.startswith("swan"):
                            _LOGGER.debug("slave is also swan type, compatible")
                        else:
                            _LOGGER.debug(
                                "device %s (hardware: %s) does not support controlling %s (hardware: %s), skip creating switch",
                                device_obj.friendly_name,
                                hardware_1,
                                slave_candidate_obj.friendly_name,
                                hardware_2,
                            )
                            continue
                    else:
                        if hardware_1 == hardware_2:
                            _LOGGER.debug("not swan but same hardware type, compatible")
                        else:
                            _LOGGER.debug(
                                "device %s (hardware: %s) does not support controlling %s (hardware: %s), skip creating switch",
                                device_obj.friendly_name,
                                hardware_1,
                                slave_candidate_obj.friendly_name,
                                hardware_2,
                            )
                            continue
                need_to_add_switch_flg = False
                slave_speaker_device_id = slave_candidate_obj.speaker_device_id
                if (
                    slave_speaker_device_id
                    in slave_speaker_device_id_to_entity_entry_dict
                ):
                    # This device already has a switch
                    entity_entry = slave_speaker_device_id_to_entity_entry_dict[
                        slave_speaker_device_id
                    ]
                    entity_id = entity_entry.entity_id
                    state_obj = self.hass.states.get(entity_id)
                    if not state_obj:
                        _LOGGER.debug(
                            "entity %s has no state (may not be initialized)", entity_id
                        )
                        need_to_add_switch_flg = True
                    else:
                        if state_obj.state == "unavailable":
                            _LOGGER.debug("entity %s state is unavailable", entity_id)
                            need_to_add_switch_flg = True
                        else:
                            _LOGGER.debug("entity %s state is available", entity_id)
                            # Update slave_device to switch
                            need_to_add_switch_flg = False
                            switch_hub = self.hivi_slave_control_switch_hub
                            switch_entity = switch_hub.get_switch(
                                unique_id=entity_entry.unique_id
                            )
                            # if switch_entity:
                            #     switch_entity.update_slave_device(slave_candidate_obj)
                else:
                    # This device does not yet have a switch
                    need_to_add_switch_flg = True

                if need_to_add_switch_flg:
                    # Create control switch
                    switch = HIVISlaveControlSwitch(
                        hass=self.hass,
                        hub=self.hivi_slave_control_switch_hub,
                        master_speaker_device_id=device_obj.speaker_device_id,
                        slave_speaker_device_id=slave_candidate_obj.speaker_device_id,
                        device_manager=self,
                        create_type="from_standalone_device",
                    )
                    _LOGGER.debug(
                        "create switch entity: %s controls %s",
                        device_obj.friendly_name,
                        slave_candidate_obj.friendly_name,
                    )
                    switches.append(switch)
                    # device_obj.switch_entities[switch.unique_id] = switch
            # Add based on slave device situation
            slave_device_list = device_obj.slave_device_list
            for slave_device in slave_device_list:
                slave_uuid = slave_device.uuid
                unique_id = f"{device_obj.speaker_device_id}_slave_{slave_uuid}"
                # if unique_id in slave_speaker_device_id_to_entity_entry_dict:
                #     # This device already has a switch
                #     continue
                need_to_add_switch_flg = False
                existing_entiy_entry_list = await self._get_entities_for_device(
                    ha_device.id
                )
                for entity_entry in existing_entiy_entry_list:
                    if entity_entry.unique_id == unique_id:
                        # This device already has a switch
                        _LOGGER.debug(
                            "device %s already has a switch to control slave device %s, judge status",
                            device_obj.friendly_name,
                            slave_device.friendly_name,
                        )
                        entity_id = entity_entry.entity_id
                        state_obj = self.hass.states.get(entity_id)
                        if not state_obj:
                            _LOGGER.debug(
                                "entity %s has no state (may not be initialized)",
                                entity_id,
                            )
                            need_to_add_switch_flg = True
                        elif state_obj.state == "unavailable":
                            _LOGGER.debug("entity %s state is unavailable", entity_id)
                            need_to_add_switch_flg = True
                        else:
                            _LOGGER.debug(
                                "entity %s state is available, no need to add again",
                                entity_id,
                            )
                            need_to_add_switch_flg = False
                        break
                else:
                    # This device does not yet have a switch
                    _LOGGER.debug(
                        "through slave device list to create switch for master speaker %s to control slave speaker %s",
                        device_obj.friendly_name,
                        slave_device.friendly_name,
                    )
                    need_to_add_switch_flg = True

                if need_to_add_switch_flg:
                    # Create control switch
                    switch = HIVISlaveControlSwitch(
                        hass=self.hass,
                        hub=self.hivi_slave_control_switch_hub,
                        master_speaker_device_id=device_obj.speaker_device_id,
                        slave_speaker_device_id=slave_device.uuid,
                        device_manager=self,
                        create_type="from_slave_device",
                    )
                    _LOGGER.debug(
                        "through slave device list to create switch for master speaker %s to control slave speaker %s",
                        device_obj.friendly_name,
                        slave_device.friendly_name,
                    )
                    switches.append(switch)
            # Add
            if switches:
                switch_cb = self._add_entities_callbacks.get("switch")
                if switch_cb:
                    switch_cb(switches, update_before_add=False)
                else:
                    _LOGGER.debug(
                        "no registered 'switch' add callback, skip adding switch entities"
                    )

    async def _get_devices_for_device(self):
        """Get all devices under integration"""
        devices = []
        device_registry = dr.async_get(self.hass)
        for device in device_registry.devices.values():
            for identifier in device.identifiers:
                if identifier[0] == DOMAIN:
                    # Devices belonging to our integration
                    devices.append(device)
        return devices

    async def _get_entities_for_device(self, ha_device_id):
        """Get all entities under device"""
        entity_registry = er.async_get(self.hass)
        entities = []
        for entity_entry in entity_registry.entities.values():
            if entity_entry.device_id == ha_device_id:
                entities.append(entity_entry)
        return entities

    async def _update_device_entity_states(self):
        """update device all entity states"""

        ha_device_list = await self._get_devices_for_device()

        for ha_device in ha_device_list:
            # 获取设备的所有实体
            existing_entiy_entry_list = await self._get_entities_for_device(
                ha_device.id
            )

            device_dict = self.device_data_registry.get_device_dict_by_ha_device_id(
                ha_device.id, default=None
            )
            if device_dict is None:
                _LOGGER.warning(
                    "can not get device data by ha_device_id, skip switch processing: ha_device_id = %s",
                    ha_device.id,
                )
                continue

            device_obj = HIVIDevice(**device_dict)

            for entity_entry in existing_entiy_entry_list:
                if entity_entry.entity_id.startswith(
                    "switch."
                ) and entity_entry.unique_id.startswith(
                    f"{device_obj.speaker_device_id}_slave_"
                ):
                    slave_device_uuid_list = [
                        sd.uuid for sd in device_obj.slave_device_list
                    ]
                    switch = self.hivi_slave_control_switch_hub.get_switch(
                        entity_entry.unique_id
                    )
                    if switch:
                        slave_speaker_device_id = entity_entry.unique_id.split(
                            "_slave_"
                        )[-1]

                        if slave_speaker_device_id in slave_device_uuid_list:
                            # Set switch to on
                            switch.on_off_switch(True)
                        else:
                            # Set switch to off
                            switch.on_off_switch(False)
                    else:
                        _LOGGER.debug(
                            f"can not find switch entity entity_entry.unique_id = {entity_entry.unique_id}"
                        )

    async def _device_offline_process(self):
        """Handle offline devices"""

        ha_device_list = await self._get_devices_for_device()

        for ha_device in ha_device_list:
            # 获取设备的所有实体
            existing_entiy_entry_list = await self._get_entities_for_device(
                ha_device.id
            )

            device_dict = self.device_data_registry.get_device_dict_by_ha_device_id(
                ha_device.id, default=None
            )
            if device_dict is None:
                _LOGGER.warning(
                    "can not get device data by ha_device_id, skip switch processing: ha_device_id = %s",
                    ha_device.id,
                )
                continue

            device_obj = HIVIDevice(**device_dict)
            time_since_last_seen = (
                datetime.now() - device_obj.last_seen
            ).total_seconds()
            _LOGGER.debug(
                "device %s time_since_last_seen: %.2f seconds",
                device_obj.friendly_name,
                time_since_last_seen,
            )

            if time_since_last_seen > DEVICE_OFFLINE_THRESHOLD:
                _LOGGER.info(
                    "device %s has been offline for more than %.2f seconds, setting all its entity states to unavailable",
                    device_obj.friendly_name,
                    DEVICE_OFFLINE_THRESHOLD,
                )
                # Update device status为离线
                device_obj.connection_status = ConnectionStatus.OFFLINE
                device_dict_new = device_obj.model_dump()
                # Save to device data registry
                self.device_data_registry.set_device_dict_by_ha_device_id(
                    ha_device.id,
                    device_dict_new,
                )
                # Set entity state to unavailable
                for entity_entry in existing_entiy_entry_list:
                    _LOGGER.debug(
                        "set device %s's entity %s state to unavailable",
                        device_obj.friendly_name,
                        entity_entry.entity_id,
                    )
                    entity_id = entity_entry.entity_id
                    if entity_id and entity_id in self.hass.states.async_entity_ids():
                        # Set entity state to unavailable through state machine
                        self.hass.states.async_set(
                            entity_id=entity_id,
                            new_state="unavailable",
                            attributes=self.hass.states.get(
                                entity_id
                            ).attributes.copy(),
                        )
                        # entity_registry = er.async_get(self.hass)
                        # entity_registry.async_update_entity(
                        #     entity_id, disabled_by=er.RegistryEntryDisabler.USER
                        # )

    async def async_manual_discovery(self):
        """Manually trigger device discovery"""
        _LOGGER.debug("manually trigger discovery")

        # Execute discovery immediately
        await self.discovery_scheduler.schedule_immediate_discovery(force=False)

    async def async_cleanup(self):
        """Clean up resources"""
        _LOGGER.debug("cleanup device manager resources")
        # self._discovery_running = False
        # if self.discovery_task:
        #     self.discovery_task.cancel()
        #     try:
        #         await self.discovery_task
        #     except asyncio.CancelledError:
        #         pass
        await self.discovery_scheduler.async_stop()
        await self.group_coordinator.async_stop()
        # Unsubscribe when unloading
        if hasattr(self, "_unsub_discovery") and self._unsub_discovery:
            self._unsub_discovery()

        # Cancel and wait for background task to finish
        if self._handle_discovery_worker:
            self._handle_discovery_worker.cancel()
            try:
                await self._handle_discovery_worker
            except asyncio.CancelledError:
                _LOGGER.debug("cancelled discovery worker")
            finally:
                self._handle_discovery_worker = None

        await self.device_data_registry.async_shutdown()

    async def refresh_discovery(self):
        _LOGGER.debug("refresh_discovery")
        await self.discovery_scheduler.schedule_immediate_discovery(force=False)

    async def postpone_discovery(self):
        _LOGGER.debug("postpone_discovery")
        await self.discovery_scheduler.postpone_discovery(DISCOVERY_BASE_INTERVAL)

    async def async_register_device(self, device_obj: HIVIDevice) -> None:
        """Register device in Home Assistant"""
        device_registry = dr.async_get(self.hass)
        # Create device
        device_entry = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, device_obj.speaker_device_id)},
            name=device_obj.friendly_name,
            manufacturer=device_obj.manufacturer,
            model=device_obj.model,
            suggested_area=self._suggest_area_from_name(device_obj.friendly_name),
            sw_version=device_obj.private_protocol_version,
            configuration_url=f"http://www.hivi.com",
        )

        # Save device entry ID
        # device_obj.ha_device_id = device_entry.id

        _LOGGER.debug(
            "register device to ha complete: %s (ID: %s)",
            device_obj.friendly_name,
            device_entry.id,
        )

        return device_entry.id

    def _suggest_area_from_name(self, name: str) -> Optional[str]:
        """Infer area from device name"""
        name_lower = name.lower()
        if "living" in name_lower or "living room" in name_lower:
            return "living room"
        elif "bedroom" in name_lower or "bed room" in name_lower:
            return "bed room"
        elif "kitchen" in name_lower or "kitchen" in name_lower:
            return "kitchen"
        elif "bathroom" in name_lower or "bathroom" in name_lower:
            return "bathroom"
        return None

    def _create_device_obj_from_discovered_device_info(self, device_info):
        """Create device from private protocol information"""
        return HIVIDevice(
            speaker_device_id=device_info.get("UDN"),
            unique_id=device_info.get("UDN"),
            friendly_name=device_info.get("friendly_name", "SWAN HiVi"),
            model=device_info.get("model_name", "Unknown"),
            manufacturer=device_info.get("manufacturer", "SWAN HiVi"),
            ha_device_id="",
            ip_addr=device_info.get("ip_addr", ""),
            mac_address=device_info.get("mac_address", ""),
            hostname=device_info.get("hostname", ""),
            supports_dlna=True,
            supports_private_protocol=True,
            sync_group_status=SyncGroupStatus.STANDALONE,
            connection_status=ConnectionStatus.ONLINE,
            last_seen=datetime.now(),
            # Master-slave relationship
            master_speaker_device_id="",  # Master speaker ID,
            slave_device_num=0,
            slave_device_list=list(),
            # DLNA information
            dlna_udn="",
            dlna_location="",
            # Private protocol information
            private_protocol_version="",
            private_port=9527,
            # Home Assistant integration
            entity_id="",
            config_entry_id="",
            # switch_entities: dict = field(default_factory=dict)
            # Other info
            wifi_channel="0",
            ssid="",
            auth_mode="",
            encryption_mode="",
            psk="",
            uuid="",
        )

    async def remove_control_entities_by_speaker_device_id(
        self, speaker_device_id: str
    ):
        """Delete control entities associated with specified speaker device ID"""
        hass = self.hass

        try:
            # Get registries
            ent_reg = er.async_get(hass)

            # Traverse all entities to find entities associated with specified speaker device ID
            entities_to_remove = []
            for entity_entry in ent_reg.entities.values():
                if entity_entry.unique_id.endswith(f"_slave_{speaker_device_id}"):
                    entities_to_remove.append(entity_entry.entity_id)

            if not entities_to_remove:
                _LOGGER.debug(
                    "can not find control entities associated with speaker device ID %s, skip deletion",
                    speaker_device_id,
                )
                return

            # Delete found entities
            for entity_id in entities_to_remove:
                ent_reg.async_remove(entity_id)
                _LOGGER.debug(
                    "removed control entities associated with speaker device ID %s: %s",
                    speaker_device_id,
                    entity_id,
                )

        except Exception as err:
            _LOGGER.error(
                "error when deleting control entities associated with speaker device ID %s: %s",
                speaker_device_id,
                err,
                exc_info=True,
            )
