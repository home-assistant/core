"""DataUpdateCoordinator for the BACnet integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import dataclass, field
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .bacnet_client import BACnetClient, BACnetDeviceInfo, BACnetObjectInfo
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_SELECTED_OBJECTS,
    DOMAIN,
    REDISCOVERY_INTERVAL,
    UPDATE_INTERVAL,
)


@dataclass
class BACnetDeviceData:
    """Store data for a BACnet device."""

    device_info: BACnetDeviceInfo
    objects: list[BACnetObjectInfo] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)


class BACnetDeviceCoordinator(DataUpdateCoordinator[BACnetDeviceData]):
    """Coordinate data updates for a single BACnet device."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_config: dict[str, Any],
        client: BACnetClient,
        device_info: BACnetDeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_info = device_info
        self._device_address: str = device_config[CONF_DEVICE_ADDRESS]
        self._device_id: int = device_config[CONF_DEVICE_ID]
        self._selected_objects: list[str] = device_config.get(CONF_SELECTED_OBJECTS, [])
        self._cov_subscription_keys: list[str] = []
        self._cov_values: dict[str, Any] = {}
        self._initial_setup_done = False
        self._background_setup_task: asyncio.Task | None = None

        # Callback lists for dynamic entity creation (Hydrawise pattern)
        self.new_objects_callbacks: list[Callable[[list[BACnetObjectInfo]], None]] = []

        # Track known objects for re-discovery change detection
        self._known_object_keys: set[str] = set()
        self._known_object_metadata: dict[str, BACnetObjectInfo] = {}
        self._last_rediscovery: float | None = None

        super().__init__(
            hass,
            logging.getLogger(__name__),
            config_entry=config_entry,
            name=f"BACnet device {device_info.name or device_info.device_id}",
            update_interval=UPDATE_INTERVAL,
        )

    @property
    def selected_objects(self) -> list[str]:
        """Return the list of selected objects for this device."""
        return self._selected_objects

    @property
    def initial_setup_done(self) -> bool:
        """Return whether initial setup has completed."""
        return self._initial_setup_done

    @property
    def cov_subscription_count(self) -> int:
        """Return the number of active COV subscriptions."""
        return len(self._cov_subscription_keys)

    async def _async_setup(self) -> None:
        """Set up the coordinator by discovering objects and subscribing to COV."""
        # Initialize with empty data - objects will be discovered in first update
        self.data = BACnetDeviceData(
            device_info=self.device_info,
            objects=[],
            values={},
        )

    async def _setup_cov_subscriptions(self, objects: list[BACnetObjectInfo]) -> None:
        """Set up COV subscriptions for objects that support it."""
        cov_supported_types = {
            "analog-input",
            "analog-output",
            "analog-value",
            "binary-input",
            "binary-output",
            "binary-value",
            "multi-state-input",
            "multi-state-output",
            "multi-state-value",
            "large-analog-value",
            "integer-value",
            "positive-integer-value",
            "lighting-output",
        }

        # Filter objects that support COV
        cov_objects = [obj for obj in objects if obj.object_type in cov_supported_types]

        if not cov_objects:
            return

        # Process one at a time to be robust and not overwhelm event loop
        for i, obj in enumerate(cov_objects, 1):
            try:
                sub_key = await self.client.subscribe_cov(
                    self._device_address,
                    obj.object_type,
                    obj.object_instance,
                    self._make_cov_callback(obj.object_type, obj.object_instance),
                )
                if sub_key:
                    self._cov_subscription_keys.append(sub_key)
            except Exception:  # noqa: BLE001
                pass

            # Yield control to event loop every 10 operations
            if i % 10 == 0:
                await asyncio.sleep(0)

    def _make_cov_callback(self, object_type: str, object_instance: int) -> Any:
        """Create a COV callback for a specific object."""
        obj_key = f"{object_type},{object_instance}"

        @callback
        def _cov_update(values: dict[str, Any]) -> None:
            """Handle a COV notification."""
            if "presentValue" in values:
                self._cov_values[obj_key] = values["presentValue"]
                if self.data is not None:
                    self.data.values[obj_key] = values["presentValue"]
                self.async_set_updated_data(self.data)

        return _cov_update

    async def _async_update_data(self) -> BACnetDeviceData:
        """Fetch data from the BACnet device."""
        if self.data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data",
            )

        # Discover objects on first update if not already done (quick mode for fast UI)
        if not self.data.objects:
            try:
                objects = await self.client.get_device_objects(
                    self._device_address,
                    self._device_id,
                    quick=True,  # Fast mode - only read object names
                )
                self.data.objects = objects

                # Populate tracking state for re-discovery
                self._known_object_keys = {
                    f"{obj.object_type},{obj.object_instance}" for obj in objects
                }
                self._known_object_metadata = {
                    f"{obj.object_type},{obj.object_instance}": obj for obj in objects
                }
                self._last_rediscovery = time.monotonic()

                # Skip COV setup and polling during initial setup
                if not self._initial_setup_done:
                    return self.data

                # Set up COV subscriptions for discovered objects
                await self._setup_cov_subscriptions(objects)
            except Exception:  # noqa: BLE001
                # Don't raise - allow retry on next update
                return self.data

        # Periodic re-discovery of objects
        if self._should_rediscover():
            await self._async_rediscover_objects()

        # Only poll objects that don't have active COV subscriptions
        cov_keys = {
            key.split(":", 1)[1] if ":" in key else key
            for key in self._cov_subscription_keys
        }

        # Build list of objects to poll
        objects_to_poll = []
        for obj in self.data.objects:
            obj_key = f"{obj.object_type},{obj.object_instance}"
            # Skip if we have a COV subscription for this object and have
            # received at least one update
            if obj_key in cov_keys and obj_key in self._cov_values:
                continue
            objects_to_poll.append((obj_key, obj.object_type, obj.object_instance))

        if objects_to_poll:
            # Process one at a time to be robust and not overwhelm event loop
            for i, (obj_key, obj_type, obj_inst) in enumerate(objects_to_poll, 1):
                try:
                    obj_key, value = await self._poll_object(
                        obj_key, obj_type, obj_inst
                    )
                    self.data.values[obj_key] = value
                except Exception:  # noqa: BLE001
                    pass

                # Yield control to event loop every 10 operations
                if i % 10 == 0:
                    await asyncio.sleep(0)

        return self.data

    async def _poll_object(
        self,
        obj_key: str,
        object_type: str,
        object_instance: int,
    ) -> tuple[str, Any]:
        """Poll a single object's present value."""
        try:
            value = await self.client.read_present_value(
                self._device_address, object_type, object_instance
            )
        except BaseException:  # noqa: BLE001
            # Some objects don't have presentValue property
            # BACpypes3 errors may not inherit from Exception
            # Return None instead of raising
            return (obj_key, None)
        else:
            return (obj_key, value)

    def _should_rediscover(self) -> bool:
        """Return whether it is time to re-discover objects."""
        if not self._initial_setup_done:
            return False
        if self._last_rediscovery is None:
            return True
        return (
            time.monotonic() - self._last_rediscovery
            >= REDISCOVERY_INTERVAL.total_seconds()
        )

    async def _async_rediscover_objects(self) -> None:
        """Re-read the device object list and detect changes."""
        self._last_rediscovery = time.monotonic()
        try:
            new_objects = await self.client.get_device_objects(
                self._device_address,
                self._device_id,
                quick=False,
            )
        except Exception:  # noqa: BLE001
            return

        new_object_map = {
            f"{obj.object_type},{obj.object_instance}": obj for obj in new_objects
        }
        new_keys = set(new_object_map)

        # Detect added objects
        added_keys = new_keys - self._known_object_keys
        if added_keys:
            added_objects = [new_object_map[k] for k in added_keys]

            # Add to coordinator data
            self.data.objects.extend(added_objects)

            # Set up COV subscriptions for new objects
            await self._setup_cov_subscriptions(added_objects)

            # Filter by selected_objects before notifying platforms
            selected = self._selected_objects
            if selected:
                added_objects = [
                    obj
                    for obj in added_objects
                    if f"{obj.object_type},{obj.object_instance}" in selected
                ]

            if added_objects:
                for cb in self.new_objects_callbacks:
                    cb(added_objects)

        # Detect removed objects
        removed_keys = self._known_object_keys - new_keys
        if removed_keys:
            self.data.objects = [
                obj
                for obj in self.data.objects
                if f"{obj.object_type},{obj.object_instance}" not in removed_keys
            ]
            await self._cleanup_cov_for_removed_objects(removed_keys)
            self._remove_stale_entities(removed_keys)

            for key in removed_keys:
                self.data.values.pop(key, None)
                self._cov_values.pop(key, None)

        # Detect changed metadata (state_text, units, name)
        for key in new_keys & self._known_object_keys:
            old_obj = self._known_object_metadata.get(key)
            new_obj = new_object_map[key]
            if old_obj and self._object_metadata_changed(old_obj, new_obj):
                for i, obj in enumerate(self.data.objects):
                    if f"{obj.object_type},{obj.object_instance}" == key:
                        self.data.objects[i] = new_obj
                        break

        # Update tracking state
        self._known_object_keys = new_keys
        self._known_object_metadata = new_object_map

    @staticmethod
    def _object_metadata_changed(old: BACnetObjectInfo, new: BACnetObjectInfo) -> bool:
        """Check if object metadata that affects entity config has changed."""
        return (
            old.state_text != new.state_text
            or old.units != new.units
            or old.object_name != new.object_name
        )

    async def _cleanup_cov_for_removed_objects(self, removed_keys: set[str]) -> None:
        """Unsubscribe COV for objects that no longer exist."""
        keys_to_remove = []
        for sub_key in self._cov_subscription_keys:
            obj_key = sub_key.split(":", 1)[1] if ":" in sub_key else sub_key
            if obj_key in removed_keys:
                keys_to_remove.append(sub_key)

        for sub_key in keys_to_remove:
            with contextlib.suppress(Exception):
                await self.client.unsubscribe_cov(sub_key)
            self._cov_subscription_keys.remove(sub_key)

    @callback
    def _remove_stale_entities(self, removed_keys: set[str]) -> None:
        """Remove entities for objects that no longer exist on the device."""
        entity_registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )
        device_id = self.device_info.device_id
        for entry in entries:
            # Unique ID format: "{device_id}-{object_type}-{object_instance}"
            prefix = f"{device_id}-"
            if entry.unique_id.startswith(prefix):
                remainder = entry.unique_id[len(prefix) :]
                parts = remainder.rsplit("-", 1)
                if len(parts) == 2:
                    obj_key = f"{parts[0]},{parts[1]}"
                    if obj_key in removed_keys:
                        entity_registry.async_remove(entry.entity_id)

    def start_background_setup(self) -> None:
        """Start background COV setup and initial polling after config entry is set up."""
        if self._background_setup_task is None:
            self._background_setup_task = asyncio.create_task(
                self._background_setup(),
                name=f"BACnet background setup {self._device_id}",
            )

    async def _background_setup(self) -> None:
        """Set up COV subscriptions and do initial polling in background."""
        try:
            # Wait a bit to let UI complete
            await asyncio.sleep(1)

            if not self.data or not self.data.objects:
                return

            # Set up COV subscriptions
            await self._setup_cov_subscriptions(self.data.objects)

            # Build list of objects to poll
            cov_keys = {
                key.split(":", 1)[1] if ":" in key else key
                for key in self._cov_subscription_keys
            }
            objects_to_poll = []
            for obj in self.data.objects:
                obj_key = f"{obj.object_type},{obj.object_instance}"
                if obj_key not in cov_keys:
                    objects_to_poll.append(
                        (obj_key, obj.object_type, obj.object_instance)
                    )

            if objects_to_poll:
                for i, (obj_key, obj_type, obj_inst) in enumerate(objects_to_poll, 1):
                    try:
                        obj_key, value = await self._poll_object(
                            obj_key, obj_type, obj_inst
                        )
                        self.data.values[obj_key] = value
                    except Exception:  # noqa: BLE001
                        pass

                    # Yield control to event loop every 10 operations
                    if i % 10 == 0:
                        await asyncio.sleep(0)

                # Notify listeners that data has been updated
                self.async_set_updated_data(self.data)

            self._initial_setup_done = True

        except Exception:  # noqa: BLE001
            pass

    async def async_shutdown(self) -> None:
        """Clean up COV subscriptions on shutdown."""
        # Cancel background setup if still running
        if self._background_setup_task and not self._background_setup_task.done():
            self._background_setup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._background_setup_task

        for sub_key in self._cov_subscription_keys:
            with contextlib.suppress(Exception):
                await self.client.unsubscribe_cov(sub_key)
        self._cov_subscription_keys.clear()
        await super().async_shutdown()
