"""Binary sensor entities for Unraid integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, STATE_ARRAY_STARTED

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import UnraidConfigEntry
    from .coordinator import (
        UnraidStorageCoordinator,
        UnraidStorageData,
        UnraidSystemCoordinator,
        UnraidSystemData,
    )
    from .models import ArrayDisk, UPSDevice

_LOGGER = logging.getLogger(__name__)

# Number of parallel update requests
PARALLEL_UPDATES = 1


class UnraidBinarySensorEntity(BinarySensorEntity):
    """Base class for Unraid binary sensor entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
        resource_id: str,
        name: str,
        server_info: dict | None = None,
    ) -> None:
        """Initialize binary sensor entity.

        Args:
            coordinator: Data coordinator
            server_uuid: Unraid server UUID
            server_name: Friendly server name
            resource_id: Resource identifier for unique_id
            name: Entity name
            server_info: Optional dict with manufacturer, model, sw_version, etc.

        """
        self.coordinator = coordinator
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

    @property
    def available(self) -> bool:
        """Return whether entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher when added to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_write_ha_state)
        )


class DiskHealthBinarySensor(UnraidBinarySensorEntity):
    """Disk health binary sensor."""

    _attr_translation_key = "disk_health"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
        disk: ArrayDisk,
    ) -> None:
        """Initialize disk health binary sensor."""
        self._disk_id = disk.id
        self._disk_name = disk.name
        super().__init__(
            coordinator=coordinator,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id=f"disk_health_{self._disk_id}",
            name=f"Disk {self._disk_name} Health",
        )

    def _get_disk(self) -> ArrayDisk | None:
        """Get current disk from coordinator data."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None:
            return None
        all_disks = data.disks + data.parities + data.caches
        for disk in all_disks:
            if disk.id == self._disk_id:
                return disk
        return None

    @property
    def is_on(self) -> bool | None:
        """Return True if disk has a problem (status != DISK_OK)."""
        disk = self._get_disk()
        if disk is None:
            return None
        if disk.status is None:
            return None
        return disk.status != "DISK_OK"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return disk details including temperature and standby as attributes."""
        disk = self._get_disk()
        if disk is None:
            return {}
        attrs: dict[str, Any] = {
            "status": disk.status,
            "device": disk.device,
        }
        # Add filesystem type if available
        if disk.fs_type:
            attrs["filesystem"] = disk.fs_type
        if disk.temp is not None:
            attrs["temperature"] = disk.temp
        if disk.smart_status:
            attrs["smart_status"] = disk.smart_status
        if disk.is_spinning is not None:
            attrs["standby"] = not disk.is_spinning
            attrs["spinning"] = disk.is_spinning
        return attrs


class ParityStatusBinarySensor(UnraidBinarySensorEntity):
    """Parity check status binary sensor.

    ON = Parity check is running or has issues (RUNNING, PAUSED, FAILED)
    OFF = Parity check completed or never run (COMPLETED, NEVER_RUN, CANCELLED)
    """

    _attr_translation_key = "parity_status"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity status binary sensor."""
        super().__init__(
            coordinator=coordinator,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_status",
            name="Parity Status",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if parity check is in progress or has issues."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None or data.parity_status is None:
            return None
        status = data.parity_status.status
        if status is None:
            return None
        # Problem states: running, paused, failed
        problem_states = {"RUNNING", "PAUSED", "FAILED"}
        return status.upper() in problem_states

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return parity check details as attributes."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None or data.parity_status is None:
            return {}
        parity = data.parity_status
        return {
            "status": parity.status.lower() if parity.status else None,
            "progress": parity.progress,
            "errors": parity.errors,
        }


class ArrayStartedBinarySensor(UnraidBinarySensorEntity):
    """Binary sensor indicating if the array is started.

    ON = Array is started/running
    OFF = Array is stopped
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "array_started"

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize array started binary sensor."""
        super().__init__(
            coordinator=coordinator,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="array_started",
            name="Array Started",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if array is started."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None or data.array_state is None:
            return None
        return data.array_state.upper() == STATE_ARRAY_STARTED


class ParityCheckRunningBinarySensor(UnraidBinarySensorEntity):
    """Binary sensor indicating if a parity check is currently running.

    ON = Parity check in progress (RUNNING or PAUSED)
    OFF = No parity check in progress
    """

    _attr_translation_key = "parity_check_running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity check running binary sensor."""
        super().__init__(
            coordinator=coordinator,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_check_running",
            name="Parity Check Running",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if parity check is running."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None or data.parity_status is None:
            return None
        status = data.parity_status.status
        if status is None:
            return None
        # Running states include RUNNING and PAUSED
        running_states = {"RUNNING", "PAUSED"}
        return status.upper() in running_states

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return parity check details as attributes."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None or data.parity_status is None:
            return {}
        parity = data.parity_status
        return {
            "status": parity.status.lower() if parity.status else None,
            "progress": parity.progress,
        }


class ParityValidBinarySensor(UnraidBinarySensorEntity):
    """Binary sensor indicating if parity is valid.

    Uses device_class=PROBLEM, so:
    ON = Parity is INVALID (problem detected)
    OFF = Parity is valid (no problem)

    Parity is considered invalid if:
    - Status is FAILED
    - Errors count > 0
    - Status is unknown/unavailable
    """

    _attr_translation_key = "parity_valid"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        server_uuid: str,
        server_name: str,
    ) -> None:
        """Initialize parity valid binary sensor."""
        super().__init__(
            coordinator=coordinator,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id="parity_valid",
            name="Parity Valid",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if parity is INVALID (problem detected)."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None or data.parity_status is None:
            return None
        parity = data.parity_status
        status = parity.status
        errors = parity.errors

        # Problem if status is FAILED or errors > 0
        is_failed = status and status.upper() == "FAILED"
        has_errors = errors is not None and errors > 0
        return is_failed or has_errors

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return parity details as attributes."""
        data: UnraidStorageData | None = self.coordinator.data
        if data is None or data.parity_status is None:
            return {}
        parity = data.parity_status
        return {
            "status": parity.status.lower() if parity.status else None,
            "errors": parity.errors,
        }


# =============================================================================
# System Binary Sensors (use UnraidSystemBinarySensor base class)
# =============================================================================


class UnraidSystemBinarySensor(BinarySensorEntity):
    """Base class for Unraid system binary sensor entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        server_uuid: str,
        server_name: str,
        resource_id: str,
        name: str,
        server_info: dict | None = None,
    ) -> None:
        """Initialize system binary sensor entity."""
        self.coordinator = coordinator
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

    @property
    def available(self) -> bool:
        """Return whether entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher when added to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_write_ha_state)
        )


class UPSConnectedBinarySensor(UnraidSystemBinarySensor):
    """Binary sensor indicating if UPS is connected.

    ON = UPS is connected and online
    OFF = UPS is not connected or offline
    """

    _attr_translation_key = "ups_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        server_uuid: str,
        server_name: str,
        ups: UPSDevice,
    ) -> None:
        """Initialize UPS connected binary sensor."""
        self._ups_id = ups.id
        self._ups_name = ups.name
        super().__init__(
            coordinator=coordinator,
            server_uuid=server_uuid,
            server_name=server_name,
            resource_id=f"ups_{ups.id}_connected",
            name="UPS Connected",
        )

    def _get_ups(self) -> UPSDevice | None:
        """Get current UPS from coordinator data."""
        data: UnraidSystemData | None = self.coordinator.data
        if data is None:
            return None
        for ups in data.ups_devices:
            if ups.id == self._ups_id:
                return ups
        return None

    @property
    def is_on(self) -> bool | None:
        """Return True if UPS is connected and online."""
        ups = self._get_ups()
        if ups is None:
            return False  # UPS not found = not connected
        # UPS is connected if it has any status (it's being reported by Unraid)
        status = ups.status
        if status is None:
            return False
        # Only consider "Offline" as disconnected, everything else means connected
        # Valid states: "Online", "On Battery", "Low Battery", "OL", "OB", etc.
        offline_states = {"Offline", "OFF"}
        return status not in offline_states

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return UPS details as attributes."""
        ups = self._get_ups()
        if ups is None:
            return {}
        return {
            "model": self._ups_name,
            "status": ups.status,
            "battery_level": ups.battery.charge_level if ups.battery else None,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    _LOGGER.debug("Setting up Unraid binary_sensor platform")

    # Get coordinators from runtime_data (HA 2024.4+ pattern)
    runtime_data = entry.runtime_data
    system_coordinator = runtime_data.system_coordinator
    storage_coordinator = runtime_data.storage_coordinator
    server_info = runtime_data.server_info

    # Server info is now a flat dict with uuid, name, manufacturer, etc.
    server_uuid = server_info.get("uuid", "unknown")
    server_name = server_info.get("name", entry.data.get("host", "Unraid"))

    entities: list[BinarySensorEntity] = []

    # Array binary sensors
    entities.append(
        ArrayStartedBinarySensor(storage_coordinator, server_uuid, server_name)
    )
    entities.append(
        ParityCheckRunningBinarySensor(storage_coordinator, server_uuid, server_name)
    )
    entities.append(
        ParityValidBinarySensor(storage_coordinator, server_uuid, server_name)
    )

    # Legacy parity status binary sensor (for backwards compatibility)
    entities.append(
        ParityStatusBinarySensor(storage_coordinator, server_uuid, server_name)
    )

    # Add disk sensors using typed coordinator data
    coordinator_data = storage_coordinator.data
    if coordinator_data:
        # Add disk health sensors for all disk types
        all_disks = (
            coordinator_data.disks + coordinator_data.parities + coordinator_data.caches
        )
        entities.extend(
            DiskHealthBinarySensor(storage_coordinator, server_uuid, server_name, disk)
            for disk in all_disks
        )

    # UPS binary sensors (only created when UPS devices are connected)
    system_data = system_coordinator.data
    if system_data and system_data.ups_devices:
        _LOGGER.debug(
            "Found %d UPS device(s), creating binary sensors",
            len(system_data.ups_devices),
        )
        entities.extend(
            UPSConnectedBinarySensor(system_coordinator, server_uuid, server_name, ups)
            for ups in system_data.ups_devices
        )
    else:
        _LOGGER.debug("No UPS devices connected, skipping UPS binary sensors")

    _LOGGER.debug("Adding %d binary_sensor entities", len(entities))
    async_add_entities(entities)
