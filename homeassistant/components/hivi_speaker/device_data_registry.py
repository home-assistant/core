import logging
from typing import Any, Dict, Optional

from homeassistant.helpers.storage import Store

from .device import ConnectionStatus, SyncGroupStatus

_LOGGER = logging.getLogger(__name__)


class DeviceDataRegistry:
    """Device data extension registry"""

    def __init__(self, hass):
        self.hass = hass
        self._store = Store(hass, 1, "hivi_speaker_device_data")
        self._device_data: Dict[str, Dict[str, Any]] = {}
        self._listeners: Dict[str, list] = {}

        async def device_registry_updated(event):
            _LOGGER.debug("Device registry updated event: %s", event.data)
            ha_device_id = event.data["device_id"]
            action = event.data["action"]
            if action == "remove":
                # Clean up data when device is deleted
                # Check if device exists
                if ha_device_id in self._device_data:
                    removed_data = self._device_data.pop(ha_device_id)
                    _LOGGER.debug(
                        "Cleaning up data for deleted device %s: %s",
                        ha_device_id,
                        removed_data,
                    )
                else:
                    _LOGGER.debug(
                        "Device %s does not exist in device_data, no cleanup needed",
                        ha_device_id,
                    )
                # # 2. Immediately persist to storage
                # await self.async_save()  # Need to add this method

        self.hass.bus.async_listen("device_registry_updated", device_registry_updated)

    async def async_load(self):
        """Load persistent data"""
        if data := await self._store.async_load():
            self._device_data = data.get("device_data", {})
        else:
            self._device_data = {}

    async def async_save(self):
        """Save device data"""
        await self._store.async_save({"device_data": self._device_data, "version": 1})

    def get_device_data(self, ha_device_id: str, key: str = None, default=None):
        """Get device data"""
        device_entry = self._device_data.get(ha_device_id, {})
        if key is None:
            return device_entry
        return device_entry.get(key, default)

    def set_device_data(self, ha_device_id: str, key: str, value: Any):
        """Set device data"""
        if ha_device_id not in self._device_data:
            self._device_data[ha_device_id] = {}

        self._device_data[ha_device_id][key] = value

        # Trigger event
        self._trigger_event(
            "device_data_updated",
            {"ha_device_id": ha_device_id, "key": key, "value": value},
        )

        # # Asynchronously save to storage
        # self.hass.async_create_task(self.async_save())

    async def async_remove_device_data(self, ha_device_id: str):
        """Remove device data (called when device is deleted)"""
        if ha_device_id in self._device_data:
            del self._device_data[ha_device_id]
            await self.async_save()

    def _trigger_event(self, event_type: str, data: Dict):
        """Trigger event"""
        for callback in self._listeners.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                _LOGGER.error("Error in event listener: %s", e)

    def add_listener(self, event_type: str, callback):
        """Add event listener"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def set_device_dict_by_ha_device_id(self, ha_device_id: str, value: Any):
        """Set device data"""
        if ha_device_id not in self._device_data:
            self._device_data[ha_device_id] = {}

        self._device_data[ha_device_id]["device_dict"] = value

        # # Asynchronously save to storage
        # self.hass.async_create_task(self.async_save())

    def get_device_dict_by_ha_device_id(
        self, ha_device_id: str, default=None
    ) -> Optional[Dict[str, Any]]:
        data = self.get_device_data(ha_device_id)
        if data:
            device_dict = data.get("device_dict")
            if device_dict and isinstance(device_dict, dict):
                return device_dict
            return default
        return default

    def get_device_dict_by_speaker_device_id(
        self, speaker_device_id: str, default=None
    ) -> Optional[Dict[str, Any]]:
        for ha_device_id in self._device_data.keys():
            data = self.get_device_data(ha_device_id)
            if data:
                device_dict = data.get("device_dict")
                if device_dict and isinstance(device_dict, dict):
                    if device_dict.get("speaker_device_id") == speaker_device_id:
                        return device_dict
                else:
                    continue
            else:
                return default
        return None

    # def get_available_slave_device_dict_list(
    #     self, exclude_speaker_device_id: str = None
    # ) -> list[dict]:
    #     """Get available slave speakers (excluding self)"""
    #     return [
    #         device_dict
    #         for device_dict in self._device_data.values()
    #         if device_dict.get("device_dict")
    #         and device_dict.get("device_dict").get("can_be_slave")
    #         and device_dict.get("device_dict").get("speaker_device_id")
    #         != exclude_speaker_device_id
    #     ]

    def get_available_slave_device_dict_list(
        self, exclude_speaker_device_id: str = None
    ) -> list[dict]:
        """Get available slave speakers (excluding self)"""

        available_devices = []

        for device_data in self._device_data.values():
            # Debug info: currently processing device
            # Can set breakpoint here when debugging
            device_dict = device_data.get("device_dict", {})
            device_id = device_dict.get("speaker_device_id", "unknown")

            # Condition 1: Check if device_dict exists
            has_device_dict = device_data.get("device_dict") is not None

            # Condition 2: Check if can be slave device
            can_be_slave = False
            if has_device_dict:
                # can_be_slave = device_data.get("can_be_slave", False)
                sync_group_status = device_dict.get("sync_group_status")
                connection_status = device_dict.get("connection_status")
                can_be_slave = (
                    sync_group_status == SyncGroupStatus.STANDALONE
                    and connection_status == ConnectionStatus.ONLINE
                )
            # Condition 3: Check if needs to be excluded
            should_exclude = False
            if exclude_speaker_device_id and has_device_dict:
                should_exclude = device_id == exclude_speaker_device_id

            # Debug info: can check all condition values here
            conditions_met = has_device_dict and can_be_slave and not should_exclude

            if conditions_met:
                # Debug info: can check details of added device
                available_devices.append(device_dict)

        # Debug info: can check final result
        return available_devices

    async def async_clear_all_data(self):
        """Clear all device data (called when integration is unloaded)"""
        _LOGGER.debug("Clearing all device data from registry")

        # 1. Clear data in memory
        self._device_data.clear()

        # 2. Clear storage file
        await self.async_save()

        # # 3. Optional: Delete storage file
        # try:
        #     store_path = self._store.path
        #     if os.path.exists(store_path):
        #         os.remove(store_path)
        #         _LOGGER.debug(f"Removed storage file: {store_path}")
        # except Exception as e:
        #     _LOGGER.error(f"Error removing storage file: {e}")

        # 4. Clear listeners
        self._listeners.clear()

        _LOGGER.debug("All device data has been cleared")
