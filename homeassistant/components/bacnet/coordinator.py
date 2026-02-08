"""DataUpdateCoordinator for the BACnet integration."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .bacnet_client import BACnetClient, BACnetDeviceInfo, BACnetObjectInfo
from .const import CONF_DEVICE_ADDRESS, CONF_DEVICE_ID, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class BACnetDeviceData:
    """Store data for a BACnet device."""

    device_info: BACnetDeviceInfo
    objects: list[BACnetObjectInfo] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)


type BACnetConfigEntry = ConfigEntry


class BACnetDeviceCoordinator(DataUpdateCoordinator[BACnetDeviceData]):
    """Coordinate data updates for a single BACnet device."""

    config_entry: BACnetConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BACnetConfigEntry,
        client: BACnetClient,
        device_info: BACnetDeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_info = device_info
        self._device_address = config_entry.data[CONF_DEVICE_ADDRESS]
        self._device_id: int = config_entry.data[CONF_DEVICE_ID]
        self._cov_subscription_keys: list[str] = []
        self._cov_values: dict[str, Any] = {}
        self._initial_setup_done = False
        self._background_setup_task: asyncio.Task | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"BACnet device {device_info.name or device_info.device_id}",
            update_interval=UPDATE_INTERVAL,
        )

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

                # Skip COV setup and polling during initial setup
                if not self._initial_setup_done:
                    return self.data

                # Set up COV subscriptions for discovered objects
                await self._setup_cov_subscriptions(objects)
            except Exception:
                _LOGGER.exception(
                    "Failed to discover objects for device %d", self._device_id
                )
                # Don't raise - allow retry on next update
                return self.data

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
                _LOGGER.warning("No objects discovered, skipping background setup")
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

        except Exception:
            _LOGGER.exception(
                "Error during background setup for device %d", self._device_id
            )

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
