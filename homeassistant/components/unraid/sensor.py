"""Sensor entities for Unraid integration using entity descriptions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import UnraidSystemCoordinator, UnraidSystemData
from .entity import UnraidSystemEntity

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
class UnraidSensorEntityDescription(SensorEntityDescription):
    """Describes an Unraid sensor entity."""

    value_fn: Callable[[UnraidSystemData], StateType]
    available_fn: Callable[[UnraidSystemData], bool] = lambda _: True


# System sensor descriptions - limited set for initial PR
SYSTEM_SENSORS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _to_float_or_none(data.metrics.cpu_percent),
    ),
    UnraidSensorEntityDescription(
        key="cpu_temp",
        translation_key="cpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _to_float_or_none(data.metrics.cpu_temperature),
        available_fn=lambda data: data.metrics.cpu_temperature is not None,
    ),
    UnraidSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _to_float_or_none(data.metrics.memory_percent),
    ),
    UnraidSensorEntityDescription(
        key="ram_used",
        translation_key="ram_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        value_fn=lambda data: _to_int_or_none(data.metrics.memory_used),
    ),
    UnraidSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        value_fn=lambda data: _parse_uptime(data.metrics.uptime),
    ),
)


class UnraidSensorEntity(UnraidSystemEntity, SensorEntity):
    """Sensor entity for Unraid system metrics."""

    entity_description: UnraidSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        description: UnraidSensorEntityDescription,
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, server_uuid, device_info)
        self.entity_description = description
        self._attr_unique_id = f"{server_uuid}_{description.key}"

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    runtime_data = entry.runtime_data
    system_coordinator = runtime_data.system_coordinator
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

    # System sensors only for initial PR
    entities.extend(
        UnraidSensorEntity(system_coordinator, description, server_uuid, device_info)
        for description in SYSTEM_SENSORS
    )

    _LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)
