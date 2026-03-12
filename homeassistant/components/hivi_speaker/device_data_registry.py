"""Device data registry for the HiVi Speaker integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .device import ConnectionStatus, SyncGroupStatus

_LOGGER = logging.getLogger(__name__)

SAVE_DELAY = 5  # seconds – batches rapid writes from a single discovery cycle


class DeviceDataRegistry:
    """Device data extension registry."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the device data registry."""
        self.hass = hass
        self._store = Store(hass, 1, "hivi_speaker_device_data")
        self._device_data: dict[str, dict[str, Any]] = {}
        self._listeners: dict[str, list] = {}

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
                    await self.async_save()
                else:
                    _LOGGER.debug(
                        "Device %s does not exist in device_data, no cleanup needed",
                        ha_device_id,
                    )

        self._unsub_device_registry = self.hass.bus.async_listen(
            "device_registry_updated", device_registry_updated
        )

    async def async_load(self):
        """Load persistent data."""
        if data := await self._store.async_load():
            self._device_data = data.get("device_data", {})
        else:
            self._device_data = {}

    async def async_save(self):
        """Save device data immediately."""
        await self._store.async_save({"device_data": self._device_data, "version": 1})

    @callback
    def _schedule_save(self) -> None:
        """Schedule a delayed save to batch rapid writes."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict:
        """Return the data dict for Store to persist."""
        return {"device_data": self._device_data, "version": 1}

    def get_device_data(self, ha_device_id: str, key: str | None = None, default=None):
        """Get device data."""
        device_entry = self._device_data.get(ha_device_id, {})
        if key is None:
            return device_entry
        return device_entry.get(key, default)

    def set_device_data(self, ha_device_id: str, key: str, value: Any):
        """Set device data."""
        if ha_device_id not in self._device_data:
            self._device_data[ha_device_id] = {}

        self._device_data[ha_device_id][key] = value
        self._schedule_save()

        self._trigger_event(
            "device_data_updated",
            {"ha_device_id": ha_device_id, "key": key, "value": value},
        )

    def get_connection_status_counts(self) -> tuple[int, int]:
        """Return (online_count, offline_count) across all tracked devices."""
        online = 0
        offline = 0
        for data in self._device_data.values():
            status = data.get("device_dict", {}).get("connection_status")
            if status == ConnectionStatus.ONLINE.value:
                online += 1
            elif status == ConnectionStatus.OFFLINE.value:
                offline += 1
        return online, offline

    async def async_remove_device_data(self, ha_device_id: str):
        """Remove device data (called when device is deleted)."""
        if ha_device_id in self._device_data:
            del self._device_data[ha_device_id]
            await self.async_save()

    def _trigger_event(self, event_type: str, data: dict):
        """Trigger event."""
        for listener_fn in self._listeners.get(event_type, []):
            try:
                listener_fn(data)
            except Exception:
                _LOGGER.exception("Error in event listener")

    def add_listener(self, event_type: str, listener):
        """Add event listener."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def set_device_dict_by_ha_device_id(self, ha_device_id: str, value: Any):
        """Set device data."""
        if ha_device_id not in self._device_data:
            self._device_data[ha_device_id] = {}

        self._device_data[ha_device_id]["device_dict"] = value
        self._schedule_save()

    def get_device_dict_by_ha_device_id(
        self, ha_device_id: str, default=None
    ) -> dict[str, Any] | None:
        """Return device dict for a given HA device ID, or default."""
        data = self.get_device_data(ha_device_id)
        if data:
            device_dict = data.get("device_dict")
            if device_dict and isinstance(device_dict, dict):
                return device_dict
            return default
        return default

    def get_device_dict_by_speaker_device_id(
        self, speaker_device_id: str, default=None
    ) -> dict[str, Any] | None:
        """Return device dict for a given speaker device ID, or default."""
        for ha_device_id in self._device_data:
            data = self.get_device_data(ha_device_id)
            if not data:
                continue
            device_dict = data.get("device_dict")
            if device_dict and isinstance(device_dict, dict):
                if device_dict.get("speaker_device_id") == speaker_device_id:
                    return device_dict
        return default

    def get_ha_device_id_by_speaker_device_id(
        self, speaker_device_id: str
    ) -> str | None:
        """Return ha_device_id for a given speaker_device_id, or None if not found."""
        for ha_device_id, data in self._device_data.items():
            device_dict = data.get("device_dict") if data else None
            if (
                isinstance(device_dict, dict)
                and device_dict.get("speaker_device_id") == speaker_device_id
            ):
                return ha_device_id
        return None

    def get_available_slave_device_dict_list(
        self, exclude_speaker_device_id: str | None = None
    ) -> list[dict]:
        """Get available slave speakers (excluding self)."""

        available_devices = []

        for device_data in self._device_data.values():
            device_dict = device_data.get("device_dict", {})
            device_id = device_dict.get("speaker_device_id", "unknown")

            has_device_dict = device_data.get("device_dict") is not None

            can_be_slave = False
            if has_device_dict:
                sync_group_status = device_dict.get("sync_group_status")
                connection_status = device_dict.get("connection_status")
                can_be_slave = (
                    sync_group_status == SyncGroupStatus.STANDALONE.value
                    and connection_status == ConnectionStatus.ONLINE.value
                )

            should_exclude = False
            if exclude_speaker_device_id and has_device_dict:
                should_exclude = device_id == exclude_speaker_device_id

            if has_device_dict and can_be_slave and not should_exclude:
                available_devices.append(device_dict)

        return available_devices

    async def async_shutdown(self):
        """Release runtime resources without deleting persistent storage.

        Called during unload/reload so cached device data survives a restart.
        """
        _LOGGER.debug("Shutting down device data registry (keeping storage)")

        if self._unsub_device_registry is not None:
            self._unsub_device_registry()
            self._unsub_device_registry = None

        # Persist any pending delayed writes before clearing memory
        await self.async_save()

        self._device_data.clear()
        self._listeners.clear()

    async def async_clear_all_data(self):
        """Clear all device data AND delete persistent storage.

        Called only when the config entry is fully removed.
        """
        _LOGGER.debug("Clearing all device data from registry (including storage)")

        if self._unsub_device_registry is not None:
            self._unsub_device_registry()
            self._unsub_device_registry = None

        self._device_data.clear()
        self._listeners.clear()

        await self.async_save()
        _LOGGER.debug("All device data has been cleared")
