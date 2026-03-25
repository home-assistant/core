"""Heiman Device Management Enhancement.

Provides comprehensive device management features:
- Device filtering (include/exclude by room, type, model)
- Hide non-standard entities
- Device debug mode
- Binary sensor display modes
- Area name synchronization strategies
- Device removal and disable options
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DeviceFilterManager:
    """Manages device filtering rules."""

    def __init__(self) -> None:
        """Initialize device filter manager."""
        self._filter_mode: str = "exclude"  # or "include"
        self._statistics_logic: str = "or"  # "and" or "or"
        self._room_filter_mode: str = "exclude"
        self._type_filter_mode: str = "exclude"
        self._model_filter_mode: str = "exclude"
        self._device_filter_mode: str = "exclude"

        # Filter lists
        self._room_list: set[str] = set()
        self._type_list: set[str] = set()
        self._model_list: set[str] = set()
        self._device_list: set[str] = set()

    def configure_filter(
        self,
        filter_mode: str = "exclude",
        statistics_logic: str = "or",
        room_filter_mode: str | None = None,
        room_list: list[str] | None = None,
        type_filter_mode: str | None = None,
        type_list: list[str] | None = None,
        model_filter_mode: str | None = None,
        model_list: list[str] | None = None,
        device_filter_mode: str | None = None,
        device_list: list[str] | None = None,
    ) -> None:
        """Configure device filter rules.

        Args:
            filter_mode: Global filter mode ("include" or "exclude")
            statistics_logic: Logic for combining filters ("and" or "or")
            room_filter_mode: Room filter mode
            room_list: List of rooms to filter
            type_filter_mode: Type filter mode
            type_list: List of device types to filter
            model_filter_mode: Model filter mode
            model_list: List of models to filter
            device_filter_mode: Device filter mode
            device_list: List of device IDs to filter
        """
        self._filter_mode = filter_mode
        self._statistics_logic = statistics_logic

        if room_filter_mode is not None:
            self._room_filter_mode = room_filter_mode
        if room_list:
            self._room_list = set(room_list)

        if type_filter_mode is not None:
            self._type_filter_mode = type_filter_mode
        if type_list:
            self._type_list = set(type_list)

        if model_filter_mode is not None:
            self._model_filter_mode = model_filter_mode
        if model_list:
            self._model_list = set(model_list)

        if device_filter_mode is not None:
            self._device_filter_mode = device_filter_mode
        if device_list:
            self._device_list = set(device_list)

        _LOGGER.info(
            "Device filter configured: mode=%s, logic=%s, rooms=%d, types=%d, models=%d, devices=%d",
            self._filter_mode,
            self._statistics_logic,
            len(self._room_list),
            len(self._type_list),
            len(self._model_list),
            len(self._device_list),
        )

    def should_include_device(self, device_info: dict) -> bool:
        """Check if a device should be included based on filter rules.

        Args:
            device_info: Device information dictionary

        Returns:
            True if device should be included, False otherwise
        """
        device_id = device_info.get("id") or device_info.get("deviceId", "")
        device_type = device_info.get("deviceType", "")
        model = device_info.get("model", "")
        room_name = device_info.get("roomName", "")

        # Collect which filters match
        matches = []

        # Check room filter
        if self._room_list:
            room_match = room_name in self._room_list
            if self._room_filter_mode == "include":
                matches.append(room_match)
            else:  # exclude
                matches.append(not room_match)

        # Check type filter
        if self._type_list:
            type_match = device_type in self._type_list
            if self._type_filter_mode == "include":
                matches.append(type_match)
            else:  # exclude
                matches.append(not type_match)

        # Check model filter
        if self._model_list:
            model_match = model in self._model_list
            if self._model_filter_mode == "include":
                matches.append(model_match)
            else:  # exclude
                matches.append(not model_match)

        # Check device filter
        if self._device_list:
            device_match = device_id in self._device_list
            if self._device_filter_mode == "include":
                matches.append(device_match)
            else:  # exclude
                matches.append(not device_match)

        # If no filters applied, include all
        if not matches:
            return True

        # Apply statistics logic
        if self._statistics_logic == "and":
            return all(matches)
        # "or"
        return any(matches)

    def get_filtered_devices(self, devices: list[dict]) -> list[dict]:
        """Filter device list based on rules.

        Args:
            devices: List of device dictionaries

        Returns:
            Filtered list of devices
        """
        filtered = []
        for device in devices:
            if self.should_include_device(device):
                filtered.append(device)
            else:
                _LOGGER.debug(
                    "Filtered out device: %s (%s)",
                    device.get("deviceName", "Unknown"),
                    device.get("id", ""),
                )

        _LOGGER.info("Device filter: %d/%d devices passed", len(filtered), len(devices))
        return filtered

    def clear_filters(self) -> None:
        """Clear all filter rules."""
        self._room_list.clear()
        self._type_list.clear()
        self._model_list.clear()
        self._device_list.clear()
        _LOGGER.info("All device filters cleared")

    @property
    def has_active_filters(self) -> bool:
        """Return whether any filter list is active."""
        return bool(
            self._room_list or self._type_list or self._model_list or self._device_list,
        )


class DeviceDisplayManager:
    """Manages device display options."""

    def __init__(self) -> None:
        """Initialize device display manager."""
        self._hide_non_standard = False
        self._action_debug_mode = False
        self._binary_sensor_display_mode = "bool"  # "bool" or "text"
        self._display_devices_changed_notify: list[str] = []

    def configure_display(
        self,
        hide_non_standard: bool = False,
        action_debug_mode: bool = False,
        binary_sensor_display_mode: str = "bool",
        display_devices_changed_notify: list[str] | None = None,
    ) -> None:
        """Configure display options.

        Args:
            hide_non_standard: Hide non-standard entities
            action_debug_mode: Enable action debug mode
            binary_sensor_display_mode: Binary sensor display mode
            display_devices_changed_notify: List of device change notifications to display
        """
        self._hide_non_standard = hide_non_standard
        self._action_debug_mode = action_debug_mode
        self._binary_sensor_display_mode = binary_sensor_display_mode

        if display_devices_changed_notify is not None:
            self._display_devices_changed_notify = display_devices_changed_notify

        _LOGGER.info(
            "Display configured: hide_non_standard=%s, action_debug=%s, binary_mode=%s",
            self._hide_non_standard,
            self._action_debug_mode,
            self._binary_sensor_display_mode,
        )

    def should_hide_entity(self, entity_name: str, is_non_standard: bool) -> bool:
        """Check if an entity should be hidden.

        Args:
            entity_name: Entity name
            is_non_standard: Whether entity is non-standard

        Returns:
            True if entity should be hidden
        """
        if self._hide_non_standard and is_non_standard:
            # Hide entities starting with "*"
            if entity_name.startswith("*"):
                return True
        return False

    def is_action_debug_enabled(self) -> bool:
        """Check if action debug mode is enabled.

        Returns:
            True if enabled
        """
        return self._action_debug_mode

    def get_binary_sensor_mode(self) -> str:
        """Get binary sensor display mode.

        Returns:
            Display mode ("bool" or "text")
        """
        return self._binary_sensor_display_mode

    def should_notify_device_change(self, device_id: str, change_type: str) -> bool:
        """Check if a device change should trigger notification.

        Args:
            device_id: Device identifier
            change_type: Type of change (e.g., "state", "property")

        Returns:
            True if should notify
        """
        if not self._display_devices_changed_notify:
            return False

        # Check if this change type is in the notification list
        return change_type in self._display_devices_changed_notify

    @property
    def hide_non_standard(self) -> bool:
        """Return whether non-standard entities should be hidden."""
        return self._hide_non_standard


class AreaNameSyncManager:
    """Manages area name synchronization strategies."""

    # Supported synchronization modes
    MODE_NONE = "none"
    MODE_ROOM = "room"
    MODE_HOME = "home"
    MODE_HOME_ROOM = "home_room"

    def __init__(self, mode: str = MODE_NONE) -> None:
        """Initialize area name sync manager.

        Args:
            mode: Synchronization mode
        """
        self._mode = mode

    def set_mode(self, mode: str) -> None:
        """Set synchronization mode.

        Args:
            mode: New mode
        """
        self._mode = mode
        _LOGGER.info("Area name sync mode set to: %s", mode)

    def get_mode(self) -> str:
        """Get current synchronization mode.

        Returns:
            Current mode
        """
        return self._mode

    def generate_area_name(
        self,
        home_name: str | None = None,
        room_name: str | None = None,
    ) -> str | None:
        """Generate area name based on sync mode.

        Args:
            home_name: Home name
            room_name: Room name

        Returns:
            Generated area name or None
        """
        if self._mode == self.MODE_NONE:
            return None

        if self._mode == self.MODE_ROOM:
            return room_name

        if self._mode == self.MODE_HOME:
            return home_name

        if self._mode == self.MODE_HOME_ROOM:
            if home_name and room_name:
                return f"{home_name} - {room_name}"
            if home_name:
                return home_name
            if room_name:
                return room_name

        return None

    def get_available_modes(self) -> dict[str, str]:
        """Get all available synchronization modes.

        Returns:
            Dictionary of mode -> description
        """
        return {
            self.MODE_NONE: "不同步 (No sync)",
            self.MODE_ROOM: "房间名 (Room name)",
            self.MODE_HOME: "家庭名 (Home name)",
            self.MODE_HOME_ROOM: "家庭名 + 房间名 (Home + Room)",
        }


class DeviceActionManager:
    """Manages device actions and debugging."""

    def __init__(self) -> None:
        """Initialize device action manager."""
        self._debug_actions: dict[str, list[dict]] = {}
        self._disabled_devices: set[str] = set()

    def enable_device_debug(self, device_id: str) -> None:
        """Enable debug mode for a device.

        Args:
            device_id: Device identifier
        """
        if device_id not in self._debug_actions:
            self._debug_actions[device_id] = []
        _LOGGER.info("Debug mode enabled for device: %s", device_id)

    def disable_device_debug(self, device_id: str) -> None:
        """Disable debug mode for a device.

        Args:
            device_id: Device identifier
        """
        if device_id in self._debug_actions:
            del self._debug_actions[device_id]
        _LOGGER.info("Debug mode disabled for device: %s", device_id)

    def is_device_debug_enabled(self, device_id: str) -> bool:
        """Check if debug mode is enabled for a device.

        Args:
            device_id: Device identifier

        Returns:
            True if debug is enabled
        """
        return device_id in self._debug_actions

    def log_debug_action(
        self,
        device_id: str,
        action: str,
        params: dict | None = None,
        result: Any | None = None,
    ) -> None:
        """Log a debug action for a device.

        Args:
            device_id: Device identifier
            action: Action name
            params: Action parameters
            result: Action result
        """
        if device_id not in self._debug_actions:
            self._debug_actions[device_id] = []

        log_entry = {
            "timestamp": __import__("time").time(),
            "action": action,
            "params": params,
            "result": result,
        }

        self._debug_actions[device_id].append(log_entry)

        # Keep only last 100 actions per device
        if len(self._debug_actions[device_id]) > 100:
            self._debug_actions[device_id] = self._debug_actions[device_id][-100:]

        _LOGGER.debug(
            "Device %s - Action: %s, Params: %s, Result: %s",
            device_id,
            action,
            params,
            result,
        )

    def get_debug_actions(self, device_id: str) -> list[dict]:
        """Get debug actions for a device.

        Args:
            device_id: Device identifier

        Returns:
            List of debug action entries
        """
        return self._debug_actions.get(device_id, [])

    def disable_device(self, device_id: str) -> None:
        """Disable a device.

        Args:
            device_id: Device identifier
        """
        self._disabled_devices.add(device_id)
        _LOGGER.info("Device disabled: %s", device_id)

    def enable_device(self, device_id: str) -> None:
        """Enable a disabled device.

        Args:
            device_id: Device identifier
        """
        self._disabled_devices.discard(device_id)
        _LOGGER.info("Device enabled: %s", device_id)

    def is_device_disabled(self, device_id: str) -> bool:
        """Check if a device is disabled.

        Args:
            device_id: Device identifier

        Returns:
            True if device is disabled
        """
        return device_id in self._disabled_devices

    @property
    def disabled_devices_count(self) -> int:
        """Return the number of disabled devices."""
        return len(self._disabled_devices)

    async def remove_device(self, device_id: str, hass: Any) -> None:
        """Remove a device from Home Assistant.

        Args:
            device_id: Device identifier
            hass: Home Assistant instance
        """
        try:
            device_reg = dr.async_get(hass)
            device_entry = device_reg.async_get_device(
                identifiers={(DOMAIN, device_id)},
            )

            if device_entry:
                device_reg.async_remove_device(device_entry.id)
                _LOGGER.info("Device removed from registry: %s", device_id)
            else:
                _LOGGER.warning("Device not found in registry: %s", device_id)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to remove device %s: %s", device_id, err)


class DeviceManagementEnhanced:
    """Enhanced device management system."""

    def __init__(self) -> None:
        """Initialize enhanced device management."""
        self._filter_manager = DeviceFilterManager()
        self._display_manager = DeviceDisplayManager()
        self._area_sync_manager = AreaNameSyncManager()
        self._action_manager = DeviceActionManager()

    def configure_all(
        self,
        filter_config: dict | None = None,
        display_config: dict | None = None,
        area_sync_mode: str | None = None,
    ) -> None:
        """Configure all device management features.

        Args:
            filter_config: Device filter configuration
            display_config: Display options configuration
            area_sync_mode: Area name synchronization mode
        """
        if filter_config:
            self._filter_manager.configure_filter(**filter_config)

        if display_config:
            self._display_manager.configure_display(**display_config)

        if area_sync_mode:
            self._area_sync_manager.set_mode(area_sync_mode)

        _LOGGER.info("Device management fully configured")

    @property
    def filter_manager(self) -> DeviceFilterManager:
        """Get filter manager instance."""
        return self._filter_manager

    @property
    def display_manager(self) -> DeviceDisplayManager:
        """Get display manager instance."""
        return self._display_manager

    @property
    def area_sync_manager(self) -> AreaNameSyncManager:
        """Get area sync manager instance."""
        return self._area_sync_manager

    @property
    def action_manager(self) -> DeviceActionManager:
        """Get action manager instance."""
        return self._action_manager

    def get_status(self) -> dict[str, Any]:
        """Get device management status.

        Returns:
            Status dictionary
        """
        return {
            "filter_active": self._filter_manager.has_active_filters,
            "hide_non_standard": self._display_manager.hide_non_standard,
            "action_debug": self._display_manager.is_action_debug_enabled(),
            "binary_mode": self._display_manager.get_binary_sensor_mode(),
            "area_sync_mode": self._area_sync_manager.get_mode(),
            "disabled_devices": self._action_manager.disabled_devices_count,
        }
