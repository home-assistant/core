"""Sensor entities for Unraid integration using entity descriptions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    UnraidStorageCoordinator,
    UnraidStorageData,
    UnraidSystemCoordinator,
    UnraidSystemData,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import UnraidConfigEntry

_LOGGER = logging.getLogger(__name__)

# Coordinator-based, no polling needed
PARALLEL_UPDATES = 0


def _get_nested(data: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is None:
            return default
    return current


def _parse_uptime(uptime_str: str | None) -> datetime | None:
    """Parse uptime datetime from string."""
    if uptime_str is None:
        return None
    # Normalize ISO format
    normalized = (
        uptime_str.replace("Z", "+00:00") if uptime_str.endswith("Z") else uptime_str
    )
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


@dataclass(frozen=True, kw_only=True)
class UnraidSystemSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid system sensor entity."""

    value_fn: Callable[[UnraidSystemData], StateType | datetime]
    available_fn: Callable[[UnraidSystemData], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class UnraidStorageSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid storage sensor entity."""

    value_fn: Callable[[UnraidStorageData], StateType]
    available_fn: Callable[[UnraidStorageData], bool] = lambda _: True


# System sensor descriptions
SYSTEM_SENSORS: tuple[UnraidSystemSensorEntityDescription, ...] = (
    UnraidSystemSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _get_nested(data.metrics, "cpu", "percentTotal"),
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _get_nested(data.metrics, "memory", "percentTotal"),
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_used",
        translation_key="ram_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested(data.metrics, "memory", "used"),
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_total",
        translation_key="ram_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested(data.metrics, "memory", "total"),
    ),
    UnraidSystemSensorEntityDescription(
        key="cpu_temp",
        translation_key="cpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            sum(temps) / len(temps)
            if (temps := _get_nested(data.info, "cpu", "packages", "temp", default=[]))
            else None
        ),
        available_fn=lambda data: bool(
            _get_nested(data.info, "cpu", "packages", "temp", default=[])
        ),
    ),
    UnraidSystemSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _parse_uptime(_get_nested(data.info, "os", "uptime")),
    ),
    UnraidSystemSensorEntityDescription(
        key="notifications",
        translation_key="notifications",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.notifications_unread,
    ),
)


# Storage sensor descriptions
STORAGE_SENSORS: tuple[UnraidStorageSensorEntityDescription, ...] = (
    UnraidStorageSensorEntityDescription(
        key="array_state",
        translation_key="array_state",
        value_fn=lambda data: (data.array_state.lower() if data.array_state else None),
    ),
    UnraidStorageSensorEntityDescription(
        key="array_usage",
        translation_key="array_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            (
                _get_nested(data.capacity, "kilobytes", "used", default=0)
                / _get_nested(data.capacity, "kilobytes", "total", default=1)
                * 100
            )
            if data.capacity and _get_nested(data.capacity, "kilobytes", "total")
            else None
        ),
        available_fn=lambda data: data.capacity is not None,
    ),
    UnraidStorageSensorEntityDescription(
        key="array_used",
        translation_key="array_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested(data.capacity, "kilobytes", "used"),
        available_fn=lambda data: data.capacity is not None,
    ),
    UnraidStorageSensorEntityDescription(
        key="array_total",
        translation_key="array_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested(data.capacity, "kilobytes", "total"),
        available_fn=lambda data: data.capacity is not None,
    ),
    UnraidStorageSensorEntityDescription(
        key="parity_progress",
        translation_key="parity_progress",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _get_nested(data.parity_status, "progress")
            if data.parity_status is not None
            else None
        ),
        available_fn=lambda data: (
            data.parity_status is not None
            and _get_nested(data.parity_status, "status") not in (None, "idle", "IDLE")
        ),
    ),
)


class UnraidSystemSensorEntity(
    CoordinatorEntity[UnraidSystemCoordinator], SensorEntity
):
    """Sensor entity for Unraid system metrics."""

    _attr_has_entity_name = True
    entity_description: UnraidSystemSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        description: UnraidSystemSensorEntityDescription,
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{server_uuid}_{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        return self.entity_description.available_fn(self.coordinator.data)


class UnraidStorageSensorEntity(
    CoordinatorEntity[UnraidStorageCoordinator], SensorEntity
):
    """Sensor entity for Unraid storage metrics."""

    _attr_has_entity_name = True
    entity_description: UnraidStorageSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        description: UnraidStorageSensorEntityDescription,
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{server_uuid}_{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        return self.entity_description.available_fn(self.coordinator.data)


@dataclass(frozen=True, kw_only=True)
class UnraidDiskSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid disk sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]
    available_fn: Callable[[dict[str, Any]], bool] = lambda _: True


# Disk sensor descriptions (created per-disk)
DISK_SENSORS: tuple[UnraidDiskSensorEntityDescription, ...] = (
    UnraidDiskSensorEntityDescription(
        key="usage",
        translation_key="disk_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda disk: (
            (disk.get("fsUsed", 0) / disk.get("fsSize", 1) * 100)
            if disk.get("fsSize")
            else None
        ),
        available_fn=lambda disk: bool(disk.get("fsSize")),
    ),
    UnraidDiskSensorEntityDescription(
        key="used",
        translation_key="disk_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: disk.get("fsUsed"),
        available_fn=lambda disk: disk.get("fsUsed") is not None,
    ),
    UnraidDiskSensorEntityDescription(
        key="temp",
        translation_key="disk_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda disk: disk.get("temp"),
        available_fn=lambda disk: disk.get("temp") is not None,
    ),
)


class UnraidDiskSensorEntity(CoordinatorEntity[UnraidStorageCoordinator], SensorEntity):
    """Sensor entity for Unraid disk metrics."""

    _attr_has_entity_name = True
    entity_description: UnraidDiskSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        description: UnraidDiskSensorEntityDescription,
        disk: dict[str, Any],
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the disk sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._disk_id = disk.get("id", "unknown")
        self._disk_name = disk.get("name", "unknown")
        self._attr_unique_id = f"{server_uuid}_disk_{self._disk_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"disk_name": self._disk_name}

    def _get_disk(self) -> dict[str, Any] | None:
        """Get current disk from coordinator data."""
        data = self.coordinator.data
        for disk in data.disks + data.parities + data.caches:
            if disk.get("id") == self._disk_id:
                return disk
        return None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        disk = self._get_disk()
        if disk is None:
            return None
        return self.entity_description.value_fn(disk)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        disk = self._get_disk()
        if disk is None:
            return False
        return self.entity_description.available_fn(disk)


@dataclass(frozen=True, kw_only=True)
class UnraidShareSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid share sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


# Share sensor descriptions (created per-share)
SHARE_SENSORS: tuple[UnraidShareSensorEntityDescription, ...] = (
    UnraidShareSensorEntityDescription(
        key="usage",
        translation_key="share_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda share: (
            (share.get("used", 0) / share.get("size", 1) * 100)
            if share.get("size")
            else None
        ),
    ),
    UnraidShareSensorEntityDescription(
        key="used",
        translation_key="share_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda share: share.get("used"),
    ),
)


class UnraidShareSensorEntity(
    CoordinatorEntity[UnraidStorageCoordinator], SensorEntity
):
    """Sensor entity for Unraid share metrics."""

    _attr_has_entity_name = True
    entity_description: UnraidShareSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidStorageCoordinator,
        description: UnraidShareSensorEntityDescription,
        share: dict[str, Any],
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the share sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._share_id = share.get("id", "unknown")
        self._share_name = share.get("name", "unknown")
        self._attr_unique_id = f"{server_uuid}_share_{self._share_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"share_name": self._share_name}

    def _get_share(self) -> dict[str, Any] | None:
        """Get current share from coordinator data."""
        for share in self.coordinator.data.shares:
            if share.get("id") == self._share_id:
                return share
        return None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        share = self._get_share()
        if share is None:
            return None
        return self.entity_description.value_fn(share)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._get_share() is not None


@dataclass(frozen=True, kw_only=True)
class UnraidUPSSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid UPS sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]
    available_fn: Callable[[dict[str, Any]], bool] = lambda _: True


# UPS sensor descriptions (created per-UPS)
UPS_SENSORS: tuple[UnraidUPSSensorEntityDescription, ...] = (
    UnraidUPSSensorEntityDescription(
        key="battery",
        translation_key="ups_battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ups: _get_nested(ups, "battery", "chargeLevel"),
    ),
    UnraidUPSSensorEntityDescription(
        key="load",
        translation_key="ups_load",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda ups: _get_nested(ups, "power", "loadPercentage"),
    ),
    UnraidUPSSensorEntityDescription(
        key="runtime",
        translation_key="ups_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda ups: _get_nested(ups, "battery", "estimatedRuntime"),
    ),
)


class UnraidUPSSensorEntity(CoordinatorEntity[UnraidSystemCoordinator], SensorEntity):
    """Sensor entity for Unraid UPS metrics."""

    _attr_has_entity_name = True
    entity_description: UnraidUPSSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        description: UnraidUPSSensorEntityDescription,
        ups: dict[str, Any],
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the UPS sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._ups_id = ups.get("id", "unknown")
        self._ups_name = ups.get("name", "unknown")
        self._attr_unique_id = f"{server_uuid}_ups_{self._ups_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"ups_name": self._ups_name}

    def _get_ups(self) -> dict[str, Any] | None:
        """Get current UPS from coordinator data."""
        for ups in self.coordinator.data.ups_devices:
            if ups.get("id") == self._ups_id:
                return ups
        return None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        ups = self._get_ups()
        if ups is None:
            return None
        return self.entity_description.value_fn(ups)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        ups = self._get_ups()
        if ups is None:
            return False
        return self.entity_description.available_fn(ups)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    runtime_data = entry.runtime_data
    system_coordinator = runtime_data.system_coordinator
    storage_coordinator = runtime_data.storage_coordinator
    server_info = runtime_data.server_info

    server_uuid = server_info.get("uuid", "unknown")
    server_name = server_info.get("name", entry.data.get("host", "Unraid"))

    # Create device info for all entities
    device_info = DeviceInfo(
        identifiers={(DOMAIN, server_uuid)},
        name=server_name,
        manufacturer=server_info.get("manufacturer"),
        model=server_info.get("model"),
        serial_number=server_info.get("serial_number"),
        sw_version=server_info.get("sw_version"),
        hw_version=server_info.get("hw_version"),
        configuration_url=server_info.get("configuration_url"),
    )

    entities: list[SensorEntity] = []

    # System sensors
    entities.extend(
        UnraidSystemSensorEntity(
            system_coordinator, description, server_uuid, device_info
        )
        for description in SYSTEM_SENSORS
    )

    # Storage sensors
    entities.extend(
        UnraidStorageSensorEntity(
            storage_coordinator, description, server_uuid, device_info
        )
        for description in STORAGE_SENSORS
    )

    # Disk sensors (per-disk, only usage for data/cache disks)
    if storage_coordinator.data:
        entities.extend(
            UnraidDiskSensorEntity(
                storage_coordinator, description, disk, server_uuid, device_info
            )
            for disk in storage_coordinator.data.disks + storage_coordinator.data.caches
            for description in DISK_SENSORS
            if disk.get("fsSize") and description.key == "usage"
        )

    # Share sensors (per-share)
    if storage_coordinator.data:
        entities.extend(
            UnraidShareSensorEntity(
                storage_coordinator, description, share, server_uuid, device_info
            )
            for share in storage_coordinator.data.shares
            for description in SHARE_SENSORS
            if description.key == "usage"
        )

    # UPS sensors (per-UPS)
    if system_coordinator.data and system_coordinator.data.ups_devices:
        entities.extend(
            UnraidUPSSensorEntity(
                system_coordinator, description, ups, server_uuid, device_info
            )
            for ups in system_coordinator.data.ups_devices
            for description in UPS_SENSORS
        )

    _LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)
