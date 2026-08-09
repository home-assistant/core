"""Support for Mikrotik routers sensors."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from typing import Any, Final, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import HEALTH, RESOURCE
from .coordinator import _LOGGER, MikrotikConfigEntry
from .entity import MikrotikEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MikrotikSensorEntityDescription(SensorEntityDescription):
    """Shared Mikrotik Sensors entity description."""

    value: Callable[[dict[str, Any]], StateType | datetime]
    type: str
    # Resource sensors are a single dict; health sensors are matched by name.
    index: int = 0
    # Preferred health metric names in priority order (first match wins).
    data_names: tuple[str, ...] | None = None


def _find_named_entry(
    data_list: Sequence[dict[str, Any]], names: tuple[str, ...]
) -> dict[str, Any] | None:
    """Return the first health entry whose name is in names."""
    by_name = {
        entry["name"]: entry
        for entry in data_list
        if isinstance(entry.get("name"), str)
    }
    for name in names:
        if name in by_name:
            return by_name[name]
    return None


def _health_numeric_value(data: dict[str, Any]) -> float | None:
    """Return a numeric health value, or None if not numeric."""
    value = data.get("value")
    if value is None:
        return None
    try:
        numeric = float(value)
    except TypeError, ValueError:
        return None
    if not isfinite(numeric):
        return None
    return numeric


def _calculate_uptime(data: dict[str, Any]) -> datetime | None:
    """Calculate uptime."""
    # e.g. 1d3h39m30s
    uptime_string = data["uptime"]

    total = 0
    num = 0

    for ch in uptime_string.strip():
        if ch.isdigit():
            num = num * 10 + int(ch)
        else:
            if ch == "w":
                total += num * (60 * 60 * 24 * 7)
            elif ch == "d":
                total += num * (60 * 60 * 24)
            elif ch == "h":
                total += num * (60 * 60)
            elif ch == "m":
                total += num * 60
            elif ch == "s":
                total += num
            else:
                _LOGGER.warning("Unknown uptime format: %s", uptime_string)
                return None

            num = 0

    if num != 0:
        _LOGGER.warning("Unknown uptime format: %s", uptime_string)
        return None

    return utcnow() - timedelta(seconds=total)


SENSORS: Final = (
    MikrotikSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=_health_numeric_value,
        type=HEALTH,
        # Newer boards expose cpu-temperature instead of temperature.
        data_names=("temperature", "cpu-temperature"),
    ),
    MikrotikSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=_health_numeric_value,
        type=HEALTH,
        data_names=("voltage",),
    ),
    MikrotikSensorEntityDescription(
        key="cpu-load",
        translation_key="cpu_load",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        value=lambda _data: _data["cpu-load"],
        type=RESOURCE,
        index=0,
    ),
    MikrotikSensorEntityDescription(
        key="memory-usage",
        translation_key="memory_usage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        value=lambda _data: (
            None
            if (total := _data.get("total-memory", 0)) == 0
            else (total - _data.get("free-memory", 0)) / total * 100
        ),
        type=RESOURCE,
        index=0,
    ),
    MikrotikSensorEntityDescription(
        key="disk-usage",
        translation_key="disk_usage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        value=lambda _data: (
            None
            if (total := _data.get("total-hdd-space", 0)) == 0
            else (total - _data.get("free-hdd-space", 0)) / total * 100
        ),
        type=RESOURCE,
        index=0,
    ),
    MikrotikSensorEntityDescription(
        key="uptime",
        device_class=SensorDeviceClass.UPTIME,
        value=_calculate_uptime,
        type=RESOURCE,
        index=0,
    ),
)


def _sensor_data_available(
    sensors: dict[str, Any], description: MikrotikSensorEntityDescription
) -> bool:
    """Return whether the coordinator has data for this sensor description."""
    data_list = sensors.get(description.type, [])
    if description.data_names is not None:
        entry = _find_named_entry(data_list, description.data_names)
        return entry is not None and _health_numeric_value(entry) is not None
    return len(data_list) >= description.index + 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MikrotikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mikrotik sensors based on a config entry."""

    coordinator = entry.runtime_data

    sensors_list = [
        MikrotikSensorEntity(coordinator, sensor_desc)
        for sensor_desc in SENSORS
        if _sensor_data_available(coordinator.api.sensors, sensor_desc)
    ]

    async_add_entities(sensors_list)


class MikrotikSensorEntity(MikrotikEntity, SensorEntity):
    """Sensor device."""

    entity_description: MikrotikSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        data_list = self.coordinator.api.sensors[self.entity_description.type]
        if self.entity_description.data_names is not None:
            data_entry = _find_named_entry(
                data_list, self.entity_description.data_names
            )
            if data_entry is None:
                return None
        else:
            data_entry = data_list[self.entity_description.index]

        return self.entity_description.value(data_entry)
