"""Sensor entities for Unraid integration using entity descriptions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from unraid_api.models import ArrayDisk, Share, UPSDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation, UnitOfPower, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_UPS_NOMINAL_POWER, DEFAULT_UPS_NOMINAL_POWER, DOMAIN
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


def _to_float_or_none(value: float | None) -> float | None:
    """Safely convert a value to float, returning None if value is None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_int_or_none(value: float | None) -> int | None:
    """Safely convert a value to int, returning None if value is None."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _format_duration(total_seconds: int | None) -> str | None:
    """Format seconds as human-readable duration string."""
    if total_seconds is None or total_seconds < 0:
        return None

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} day" if days == 1 else f"{days} days")
    if hours > 0:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if minutes > 0:
        parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} second" if seconds == 1 else f"{seconds} seconds")

    return ", ".join(parts)


def _parse_uptime(uptime: datetime | None) -> str | None:
    """Calculate uptime duration from boot time datetime."""
    if uptime is None:
        return None
    try:
        now = datetime.now(uptime.tzinfo)
        total_seconds = int((now - uptime).total_seconds())
        return _format_duration(total_seconds)
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True, kw_only=True)
class UnraidSystemSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid system sensor entity."""

    value_fn: Callable[[UnraidSystemData], StateType]
    available_fn: Callable[[UnraidSystemData], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class UnraidStorageSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid storage sensor entity."""

    value_fn: Callable[[UnraidStorageData], StateType]
    available_fn: Callable[[UnraidStorageData], bool] = lambda _: True


# System sensor descriptions - using Pydantic model attributes
SYSTEM_SENSORS: tuple[UnraidSystemSensorEntityDescription, ...] = (
    UnraidSystemSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _to_float_or_none(data.metrics.cpu_percent),
    ),
    UnraidSystemSensorEntityDescription(
        key="cpu_temp",
        translation_key="cpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _to_float_or_none(data.metrics.cpu_temperature),
        available_fn=lambda data: data.metrics.cpu_temperature is not None,
    ),
    UnraidSystemSensorEntityDescription(
        key="cpu_power",
        translation_key="cpu_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _to_float_or_none(data.metrics.cpu_power),
        available_fn=lambda data: data.metrics.cpu_power is not None,
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _to_float_or_none(data.metrics.memory_percent),
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_used",
        translation_key="ram_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        value_fn=lambda data: _to_int_or_none(data.metrics.memory_used),
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_free",
        translation_key="ram_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _to_int_or_none(data.metrics.memory_free),
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_available",
        translation_key="ram_available",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _to_int_or_none(data.metrics.memory_available),
    ),
    UnraidSystemSensorEntityDescription(
        key="ram_total",
        translation_key="ram_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _to_int_or_none(data.metrics.memory_total),
    ),
    UnraidSystemSensorEntityDescription(
        key="swap_usage",
        translation_key="swap_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _to_float_or_none(data.metrics.swap_percent),
        available_fn=lambda data: data.metrics.swap_total is not None,
    ),
    UnraidSystemSensorEntityDescription(
        key="swap_used",
        translation_key="swap_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _to_int_or_none(data.metrics.swap_used),
        available_fn=lambda data: data.metrics.swap_total is not None,
    ),
    UnraidSystemSensorEntityDescription(
        key="swap_total",
        translation_key="swap_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _to_int_or_none(data.metrics.swap_total),
        available_fn=lambda data: data.metrics.swap_total is not None,
    ),
    UnraidSystemSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        value_fn=lambda data: _parse_uptime(data.metrics.uptime),
    ),
    UnraidSystemSensorEntityDescription(
        key="docker_containers",
        translation_key="docker_containers",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data.containers),
    ),
    UnraidSystemSensorEntityDescription(
        key="docker_containers_running",
        translation_key="docker_containers_running",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(
            1 for c in data.containers if c.state and c.state.lower() == "running"
        ),
    ),
    UnraidSystemSensorEntityDescription(
        key="vms",
        translation_key="vms",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: len(data.vms),
    ),
    UnraidSystemSensorEntityDescription(
        key="vms_running",
        translation_key="vms_running",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: sum(
            1 for vm in data.vms if vm.state and vm.state.lower() == "running"
        ),
    ),
    UnraidSystemSensorEntityDescription(
        key="notifications",
        translation_key="notifications",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.notifications.unread.total,
    ),
    UnraidSystemSensorEntityDescription(
        key="notifications_warning",
        translation_key="notifications_warning",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.notifications.unread.warning,
    ),
    UnraidSystemSensorEntityDescription(
        key="notifications_alert",
        translation_key="notifications_alert",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.notifications.unread.alert,
    ),
)


# Storage sensor descriptions - using Pydantic model attributes
STORAGE_SENSORS: tuple[UnraidStorageSensorEntityDescription, ...] = (
    UnraidStorageSensorEntityDescription(
        key="array_state",
        translation_key="array_state",
        value_fn=lambda data: data.array.state.lower() if data.array.state else None,
    ),
    UnraidStorageSensorEntityDescription(
        key="array_usage",
        translation_key="array_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.array.capacity.usage_percent,
        available_fn=lambda data: data.array.capacity.kilobytes.total > 0,
    ),
    UnraidStorageSensorEntityDescription(
        key="array_used",
        translation_key="array_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        value_fn=lambda data: data.array.capacity.kilobytes.used,
        available_fn=lambda data: data.array.capacity.kilobytes.total > 0,
    ),
    UnraidStorageSensorEntityDescription(
        key="array_free",
        translation_key="array_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.array.capacity.kilobytes.free,
        available_fn=lambda data: data.array.capacity.kilobytes.total > 0,
    ),
    UnraidStorageSensorEntityDescription(
        key="array_total",
        translation_key="array_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.array.capacity.kilobytes.total,
        available_fn=lambda data: data.array.capacity.kilobytes.total > 0,
    ),
    UnraidStorageSensorEntityDescription(
        key="array_disks",
        translation_key="array_disks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: len(data.array.disks),
    ),
    UnraidStorageSensorEntityDescription(
        key="cache_disks",
        translation_key="cache_disks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: len(data.array.caches),
    ),
    UnraidStorageSensorEntityDescription(
        key="parity_disks",
        translation_key="parity_disks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: len(data.array.parities),
    ),
    UnraidStorageSensorEntityDescription(
        key="parity_progress",
        translation_key="parity_progress",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.array.parityCheckStatus.progress or 0,
        available_fn=lambda data: (
            data.array.parityCheckStatus.status is not None
            and data.array.parityCheckStatus.status.lower() not in ("idle", "")
        ),
    ),
    UnraidStorageSensorEntityDescription(
        key="parity_errors",
        translation_key="parity_errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.array.parityCheckStatus.errors or 0,
        available_fn=lambda data: (
            data.array.parityCheckStatus.status is not None
            and data.array.parityCheckStatus.status.lower() not in ("idle", "")
        ),
    ),
    UnraidStorageSensorEntityDescription(
        key="parity_speed",
        translation_key="parity_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement="MB/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(data.array.parityCheckStatus.speed / 1000, 1)
            if data.array.parityCheckStatus.speed
            else 0
        ),
        available_fn=lambda data: (
            data.array.parityCheckStatus.status is not None
            and data.array.parityCheckStatus.status.lower() not in ("idle", "")
        ),
    ),
    UnraidStorageSensorEntityDescription(
        key="flash_usage",
        translation_key="flash_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            data.array.boot.usage_percent if data.array.boot else None
        ),
        available_fn=lambda data: (
            data.array.boot is not None and data.array.boot.fsSize is not None
        ),
    ),
    UnraidStorageSensorEntityDescription(
        key="flash_used",
        translation_key="flash_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        value_fn=lambda data: data.array.boot.fsUsed if data.array.boot else None,
        available_fn=lambda data: data.array.boot is not None,
    ),
    UnraidStorageSensorEntityDescription(
        key="flash_total",
        translation_key="flash_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.array.boot.fsSize if data.array.boot else None,
        available_fn=lambda data: data.array.boot is not None,
    ),
    UnraidStorageSensorEntityDescription(
        key="shares",
        translation_key="shares",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: len(data.shares),
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

    value_fn: Callable[[ArrayDisk], StateType]
    available_fn: Callable[[ArrayDisk], bool] = lambda _: True


# Disk sensor descriptions (created per-disk) - using ArrayDisk model
DISK_SENSORS: tuple[UnraidDiskSensorEntityDescription, ...] = (
    UnraidDiskSensorEntityDescription(
        key="usage",
        translation_key="disk_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda disk: disk.usage_percent,
        available_fn=lambda disk: disk.fsSize is not None and disk.fsSize > 0,
    ),
    UnraidDiskSensorEntityDescription(
        key="used",
        translation_key="disk_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        value_fn=lambda disk: disk.fsUsed,
        available_fn=lambda disk: disk.fsUsed is not None,
    ),
    UnraidDiskSensorEntityDescription(
        key="free",
        translation_key="disk_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda disk: disk.fsFree,
        available_fn=lambda disk: disk.fsFree is not None,
    ),
    UnraidDiskSensorEntityDescription(
        key="total",
        translation_key="disk_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda disk: disk.fsSize,
        available_fn=lambda disk: disk.fsSize is not None,
    ),
    UnraidDiskSensorEntityDescription(
        key="temp",
        translation_key="disk_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda disk: disk.temp,
        available_fn=lambda disk: disk.temp is not None,
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
        disk: ArrayDisk,
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the disk sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._disk_id = disk.id
        self._disk_name = disk.name or "unknown"
        self._attr_unique_id = f"{server_uuid}_disk_{self._disk_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"disk_name": self._disk_name}

    def _get_disk(self) -> ArrayDisk | None:
        """Get current disk from coordinator data."""
        data = self.coordinator.data
        for disk in data.array.disks + data.array.parities + data.array.caches:
            if disk.id == self._disk_id:
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

    value_fn: Callable[[Share], StateType]


# Share sensor descriptions (created per-share) - using Share model
SHARE_SENSORS: tuple[UnraidShareSensorEntityDescription, ...] = (
    UnraidShareSensorEntityDescription(
        key="usage",
        translation_key="share_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda share: share.usage_percent,
    ),
    UnraidShareSensorEntityDescription(
        key="used",
        translation_key="share_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        value_fn=lambda share: share.used,
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
        share: Share,
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the share sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._share_id = share.id
        self._share_name = share.name
        self._attr_unique_id = f"{server_uuid}_share_{self._share_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"share_name": self._share_name}

    def _get_share(self) -> Share | None:
        """Get current share from coordinator data."""
        for share in self.coordinator.data.shares:
            if share.id == self._share_id:
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

    value_fn: Callable[[UPSDevice], StateType]
    available_fn: Callable[[UPSDevice], bool] = lambda _: True


# UPS sensor descriptions (created per-UPS) - using UPSDevice model
UPS_SENSORS: tuple[UnraidUPSSensorEntityDescription, ...] = (
    UnraidUPSSensorEntityDescription(
        key="battery",
        translation_key="ups_battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ups: _to_float_or_none(ups.battery.chargeLevel),
    ),
    UnraidUPSSensorEntityDescription(
        key="load",
        translation_key="ups_load",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda ups: _to_float_or_none(ups.power.loadPercentage),
    ),
    UnraidUPSSensorEntityDescription(
        key="runtime",
        translation_key="ups_runtime",
        value_fn=lambda ups: _format_duration(ups.battery.estimatedRuntime),
    ),
    UnraidUPSSensorEntityDescription(
        key="input_voltage",
        translation_key="ups_input_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda ups: _to_float_or_none(ups.power.inputVoltage),
        available_fn=lambda ups: ups.power.inputVoltage is not None,
    ),
    UnraidUPSSensorEntityDescription(
        key="output_voltage",
        translation_key="ups_output_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda ups: _to_float_or_none(ups.power.outputVoltage),
        available_fn=lambda ups: ups.power.outputVoltage is not None,
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
        ups: UPSDevice,
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the UPS sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._ups_id = ups.id
        self._ups_name = ups.name
        self._attr_unique_id = f"{server_uuid}_ups_{self._ups_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"ups_name": self._ups_name}

    def _get_ups(self) -> UPSDevice | None:
        """Get current UPS from coordinator data."""
        for ups in self.coordinator.data.ups_devices:
            if ups.id == self._ups_id:
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


class UnraidUPSPowerSensorEntity(
    CoordinatorEntity[UnraidSystemCoordinator], SensorEntity
):
    """Sensor entity for calculated UPS power consumption.

    Calculates power in Watts from: load_percentage * nominal_power / 100
    Only created when nominal_power is configured > 0.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "ups_power"

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        ups: UPSDevice,
        server_uuid: str,
        device_info: DeviceInfo,
        nominal_power: int,
    ) -> None:
        """Initialize the UPS power sensor."""
        super().__init__(coordinator)
        self._ups_id = ups.id
        self._ups_name = ups.name
        self._nominal_power = nominal_power
        self._attr_unique_id = f"{server_uuid}_ups_{self._ups_id}_power"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"ups_name": self._ups_name}

    def _get_ups(self) -> UPSDevice | None:
        """Get current UPS from coordinator data."""
        for ups in self.coordinator.data.ups_devices:
            if ups.id == self._ups_id:
                return ups
        return None

    @property
    def native_value(self) -> StateType:
        """Return calculated power consumption in Watts."""
        ups = self._get_ups()
        if ups is None:
            return None
        load = _to_float_or_none(ups.power.loadPercentage)
        if load is None:
            return None
        return round(load * self._nominal_power / 100, 1)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        return self._get_ups() is not None


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

    server_uuid = server_info.uuid or "unknown"
    server_name = server_info.hostname or entry.data.get("host", "Unraid")

    # Create device info for all entities
    device_info = DeviceInfo(
        identifiers={(DOMAIN, server_uuid)},
        name=server_name,
        manufacturer=server_info.manufacturer,
        model=server_info.model,
        serial_number=server_info.serial_number,
        sw_version=server_info.sw_version,
        hw_version=server_info.hw_version,
        configuration_url=server_info.local_url,
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
            for disk in (
                storage_coordinator.data.array.disks
                + storage_coordinator.data.array.caches
            )
            for description in DISK_SENSORS
            if disk.fsSize and description.key == "usage"
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

        # UPS Power sensor (calculated from load% * nominal_power)
        # Only created if nominal_power is configured > 0
        nominal_power = entry.options.get(
            CONF_UPS_NOMINAL_POWER, DEFAULT_UPS_NOMINAL_POWER
        )
        if nominal_power > 0:
            entities.extend(
                UnraidUPSPowerSensorEntity(
                    system_coordinator, ups, server_uuid, device_info, nominal_power
                )
                for ups in system_coordinator.data.ups_devices
            )

    _LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)
