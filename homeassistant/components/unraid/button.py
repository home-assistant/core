"""Button entities for Unraid integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

if TYPE_CHECKING:
    from unraid_api import UnraidClient

    from homeassistant.core import HomeAssistant

    from . import UnraidConfigEntry
    from .coordinator import UnraidStorageCoordinator, UnraidStorageData
    from .models import ArrayDisk

_LOGGER = logging.getLogger(__name__)

# Number of parallel update requests
PARALLEL_UPDATES = 1


class UnraidButtonEntity(ButtonEntity):
    """Base class for Unraid button entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
        resource_id: str,
        name: str,
        server_info: dict | None = None,
    ) -> None:
        """Initialize button entity."""
        self.api_client = api_client
        self._server_uuid = server_uuid
        self._server_name = server_name
        self._attr_unique_id = f"{server_uuid}_{resource_id}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, server_uuid)},
            "name": server_name,
            "manufacturer": server_info.get("manufacturer") if server_info else None,
            "model": server_info.get("model") if server_info else None,
            "serial_number": (
                server_info.get("serial_number") if server_info else None
            ),
            "sw_version": server_info.get("sw_version") if server_info else None,
            "hw_version": server_info.get("hw_version") if server_info else None,
            "configuration_url": (
                server_info.get("configuration_url") if server_info else None
            ),
        }


# =============================================================================
# Array Control Buttons
# =============================================================================


class ArrayStartButton(UnraidButtonEntity):
    """Button to start the Unraid array."""

    _attr_translation_key = "array_start"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize array start button."""
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="array_start",
            name="Start Array",
        )

    async def async_press(self) -> None:
        """Handle button press to start array."""
        _LOGGER.info("Starting Unraid array on %s", self._server_name)
        try:
            await self.api_client.start_array()
            _LOGGER.debug("Array start command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to start array: %s", err)
            raise HomeAssistantError(f"Failed to start array: {err}") from err


class ArrayStopButton(UnraidButtonEntity):
    """Button to stop the Unraid array."""

    _attr_translation_key = "array_stop"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.RESTART  # Shows confirmation in UI

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize array stop button."""
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="array_stop",
            name="Stop Array",
        )

    async def async_press(self) -> None:
        """Handle button press to stop array."""
        _LOGGER.warning("Stopping Unraid array on %s", self._server_name)
        try:
            await self.api_client.stop_array()
            _LOGGER.debug("Array stop command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to stop array: %s", err)
            raise HomeAssistantError(f"Failed to stop array: {err}") from err


# =============================================================================
# Parity Check Control Buttons
# =============================================================================


class ParityCheckStartButton(UnraidButtonEntity):
    """Button to start a parity check (read-only, no corrections)."""

    _attr_translation_key = "parity_check_start"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity check start button."""
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_check_start",
            name="Start Parity Check",
        )

    async def async_press(self) -> None:
        """Handle button press to start parity check."""
        _LOGGER.info("Starting parity check on %s", self._server_name)
        try:
            # Start check-only mode (correct=False)
            await self.api_client.start_parity_check(correct=False)
            _LOGGER.debug("Parity check start command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to start parity check: %s", err)
            raise HomeAssistantError(f"Failed to start parity check: {err}") from err


class ParityCheckStartCorrectionButton(UnraidButtonEntity):
    """Button to start a parity check with corrections enabled."""

    _attr_translation_key = "parity_check_start_correct"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity check with corrections button."""
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_check_start_correct",
            name="Start Parity Check (Correcting)",
        )

    async def async_press(self) -> None:
        """Handle button press to start parity check with corrections."""
        _LOGGER.info("Starting correcting parity check on %s", self._server_name)
        try:
            # Start with corrections enabled (correct=True)
            await self.api_client.start_parity_check(correct=True)
            _LOGGER.debug("Correcting parity check start command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to start correcting parity check: %s", err)
            raise HomeAssistantError(
                f"Failed to start correcting parity check: {err}"
            ) from err


class ParityCheckPauseButton(UnraidButtonEntity):
    """Button to pause a running parity check."""

    _attr_translation_key = "parity_check_pause"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity check pause button."""
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_check_pause",
            name="Pause Parity Check",
        )

    async def async_press(self) -> None:
        """Handle button press to pause parity check."""
        _LOGGER.info("Pausing parity check on %s", self._server_name)
        try:
            await self.api_client.pause_parity_check()
            _LOGGER.debug("Parity check pause command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to pause parity check: %s", err)
            raise HomeAssistantError(f"Failed to pause parity check: {err}") from err


class ParityCheckResumeButton(UnraidButtonEntity):
    """Button to resume a paused parity check."""

    _attr_translation_key = "parity_check_resume"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity check resume button."""
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_check_resume",
            name="Resume Parity Check",
        )

    async def async_press(self) -> None:
        """Handle button press to resume parity check."""
        _LOGGER.info("Resuming parity check on %s", self._server_name)
        try:
            await self.api_client.resume_parity_check()
            _LOGGER.debug("Parity check resume command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to resume parity check: %s", err)
            raise HomeAssistantError(f"Failed to resume parity check: {err}") from err


class ParityCheckStopButton(UnraidButtonEntity):
    """Button to stop/cancel a running parity check."""

    _attr_translation_key = "parity_check_stop"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity check stop button."""
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_check_stop",
            name="Stop Parity Check",
        )

    async def async_press(self) -> None:
        """Handle button press to stop parity check."""
        _LOGGER.warning("Stopping parity check on %s", self._server_name)
        try:
            await self.api_client.cancel_parity_check()
            _LOGGER.debug("Parity check stop command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to stop parity check: %s", err)
            raise HomeAssistantError(f"Failed to stop parity check: {err}") from err


# =============================================================================
# Disk Spin Control Buttons
# =============================================================================


class DiskSpinUpButton(UnraidButtonEntity):
    """Button to spin up a disk."""

    _attr_translation_key = "disk_spin_up"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        api_client: UnraidClient,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
        disk: ArrayDisk,
    ) -> None:
        """Initialize disk spin up button."""
        self._disk_id = disk.id
        self._disk_name = disk.name or disk.id
        self.coordinator = coordinator
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id=f"disk_spin_up_{disk.id}",
            name=f"Spin Up {self._disk_name}",
        )

    async def async_press(self) -> None:
        """Handle button press to spin up disk."""
        _LOGGER.info("Spinning up disk %s on %s", self._disk_name, self._server_name)
        try:
            await self.api_client.spin_up_disk(self._disk_id)
            _LOGGER.debug("Disk spin up command sent successfully")
            # Request coordinator refresh to update disk state
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to spin up disk %s: %s", self._disk_name, err)
            raise HomeAssistantError(
                f"Failed to spin up disk {self._disk_name}: {err}"
            ) from err


class DiskSpinDownButton(UnraidButtonEntity):
    """Button to spin down a disk."""

    _attr_translation_key = "disk_spin_down"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        api_client: UnraidClient,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
        disk: ArrayDisk,
    ) -> None:
        """Initialize disk spin down button."""
        self._disk_id = disk.id
        self._disk_name = disk.name or disk.id
        self.coordinator = coordinator
        super().__init__(
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id=f"disk_spin_down_{disk.id}",
            name=f"Spin Down {self._disk_name}",
        )

    async def async_press(self) -> None:
        """Handle button press to spin down disk."""
        _LOGGER.info("Spinning down disk %s on %s", self._disk_name, self._server_name)
        try:
            await self.api_client.spin_down_disk(self._disk_id)
            _LOGGER.debug("Disk spin down command sent successfully")
            # Request coordinator refresh to update disk state
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to spin down disk %s: %s", self._disk_name, err)
            raise HomeAssistantError(
                f"Failed to spin down disk {self._disk_name}: {err}"
            ) from err


# =============================================================================
# Platform Setup
# =============================================================================


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities."""
    _LOGGER.debug("Setting up Unraid button platform")

    # Get coordinators and API client from runtime_data (HA 2024.4+ pattern)
    runtime_data = entry.runtime_data
    storage_coordinator = runtime_data.storage_coordinator
    api_client = runtime_data.api_client
    server_info = runtime_data.server_info

    # Server info is now a flat dict with uuid, name, manufacturer, etc.
    server_uuid = server_info.get("uuid", "unknown")
    server_name = server_info.get("name", entry.data.get("host", "Unraid"))

    entities: list[ButtonEntity] = []

    # Array control buttons
    entities.append(ArrayStartButton(api_client, server_uuid, server_name))
    entities.append(ArrayStopButton(api_client, server_uuid, server_name))

    # Parity check control buttons
    entities.append(ParityCheckStartButton(api_client, server_uuid, server_name))
    entities.append(ParityCheckStopButton(api_client, server_uuid, server_name))

    # Disk spin control buttons (per disk)
    if storage_coordinator and storage_coordinator.data:
        coordinator_data: UnraidStorageData = storage_coordinator.data
        # Add spin buttons for all disks (data disks, parity, cache)
        all_disks = (
            coordinator_data.disks + coordinator_data.parities + coordinator_data.caches
        )
        for disk in all_disks:
            entities.append(
                DiskSpinUpButton(
                    api_client, storage_coordinator, server_uuid, server_name, disk
                )
            )
            entities.append(
                DiskSpinDownButton(
                    api_client, storage_coordinator, server_uuid, server_name, disk
                )
            )

    _LOGGER.debug("Adding %d button entities", len(entities))
    async_add_entities(entities)
